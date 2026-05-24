#!/usr/bin/env bash
# =============================================================================
# Kingstore SaaS — demo tenant seeder
# Runs against a live API (default: http://127.0.0.1:8001).
# Creates a polished mobile-shop tenant with realistic Arabic data
# so the demo URL looks alive from minute zero.
# =============================================================================
set -euo pipefail

API="${API:-http://127.0.0.1:8001}"
SLUG="${SLUG:-demo}"
TENANT_NAME="${TENANT_NAME:-Kingstore Demo}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@kingstore.demo}"
ADMIN_PASS="${ADMIN_PASS:-Demo12345678}"

say() { printf "\n\033[1;34m==>\033[0m %s\n" "$*"; }

# --- 1. Signup --------------------------------------------------------------
say "Signing up tenant '$SLUG'..."
SIGNUP_RESP=$(curl -sS -X POST "$API/api/v1/auth/signup" \
    -H "Content-Type: application/json" \
    -d "{
        \"tenant_slug\": \"$SLUG\",
        \"tenant_name\": \"$TENANT_NAME\",
        \"owner_name\": \"المدير العام\",
        \"owner_email\": \"$ADMIN_EMAIL\",
        \"owner_username\": \"$ADMIN_USER\",
        \"owner_password\": \"$ADMIN_PASS\",
        \"default_branch_name\": \"الفرع الرئيسي\",
        \"default_branch_code\": \"MAIN\"
    }")
TOKEN=$(echo "$SIGNUP_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['tokens']['access_token'])")
BRANCH_ID=$(echo "$SIGNUP_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['user']['default_branch_id'])")
H=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")
echo "  tenant created, branch_id=$BRANCH_ID"

# --- 2. Products ------------------------------------------------------------
say "Creating products..."
declare -A PIDS
make_product() {
    local name="$1" name_ar="$2" cat="$3" code="$4" cost="$5" price="$6" qty="$7"
    local resp
    resp=$(curl -sS -X POST "$API/api/v1/products/" "${H[@]}" -d "{
        \"name\": \"$name\",
        \"name_ar\": \"$name_ar\",
        \"category\": \"$cat\",
        \"code\": \"$code\",
        \"cost\": \"$cost\",
        \"price\": \"$price\",
        \"reorder_point\": 3
    }")
    local pid
    pid=$(echo "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['id'])")
    PIDS["$code"]="$pid"
    echo "  + $name_ar ($code)"

    # Opening stock via adjustment
    curl -sS -X POST "$API/api/v1/inventory/adjust" "${H[@]}" -d "{
        \"product_id\": \"$pid\",
        \"branch_id\": \"$BRANCH_ID\",
        \"qty\": $qty,
        \"direction\": \"in\",
        \"reason\": \"رصيد افتتاحي\"
    }" >/dev/null
}

make_product "iPhone 15 128GB"   "آيفون 15 - 128 جيجا"     mobile     M-IPH15   28000  35000  6
make_product "iPhone 15 Pro Max" "آيفون 15 برو ماكس"        mobile     M-IPH15PM 48000  58000  4
make_product "Samsung S24 Ultra" "سامسونج S24 ألترا"        mobile     M-S24U    42000  52000  5
make_product "Samsung A55"       "سامسونج A55"              mobile     M-A55     10500  13000  10
make_product "Xiaomi Redmi 13"   "شاومي ريدمي 13"           mobile     M-RD13    4200   5500   12
make_product "Anker Charger 65W" "شاحن أنكر 65 وات"         accessory  A-ANK65   1100   1500   25
make_product "USB-C Cable 1m"    "كابل USB-C - 1 متر"       accessory  A-USBC1   80     150    80
make_product "Glass Protector"   "واقي شاشة زجاجي"          accessory  A-GLASS   45     120    100
make_product "Bluetooth Earbuds" "سماعات بلوتوث"            accessory  A-BTEB    650    1200   30
make_product "Battery iPhone 13" "بطارية آيفون 13"          spare      S-BIPH13  650    1200   15
make_product "Battery Samsung"   "بطارية سامسونج عامة"     spare      S-BSAM    400    800    20
make_product "Charging IC"       "آي سي شحن"                spare      S-CIC     180    450    40
make_product "Screen Repair"     "صيانة شاشة"               service    SVC-SCR   0      0      0
make_product "Software Service"  "خدمة سوفت وير"            service    SVC-SW    0      0      0

# --- 3. Customers -----------------------------------------------------------
say "Creating customers..."
declare -A CIDS
make_customer() {
    local name="$1" phone="$2" key="$3"
    local resp
    resp=$(curl -sS -X POST "$API/api/v1/customers/" "${H[@]}" -d "{
        \"name\": \"$name\",
        \"phone\": \"$phone\"
    }")
    local cid
    cid=$(echo "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['id'])")
    CIDS["$key"]="$cid"
    echo "  + $name"
}
make_customer "أحمد محمد علي"     "01001234567" ahmed
make_customer "سارة عبد الرحمن"    "01112345678" sara
make_customer "محمود إبراهيم"      "01223456789" mahmoud
make_customer "نهى السيد"          "01034567890" noha
make_customer "كريم حسن"           "01545678901" karim
make_customer "عميل نقدي"          "00000000000" walkin

# --- 4. Suppliers -----------------------------------------------------------
say "Creating suppliers..."
make_supplier() {
    local name="$1" phone="$2"
    curl -sS -X POST "$API/api/v1/suppliers/" "${H[@]}" -d "{
        \"name\": \"$name\",
        \"phone\": \"$phone\"
    }" >/dev/null
    echo "  + $name"
}
make_supplier "مكتب الموبايلات الذكية" "0223456789"
make_supplier "Tech World للجملة"       "0234567890"
make_supplier "إكسسوارات النيل"          "0245678901"

# --- 5. Sales (cash + credit) -----------------------------------------------
say "Creating sample sales..."
# Customer names map (for repairs which want a free-text name even when linked)
declare -A CNAMES
CNAMES[ahmed]="أحمد محمد علي"
CNAMES[sara]="سارة عبد الرحمن"
CNAMES[mahmoud]="محمود إبراهيم"
CNAMES[noha]="نهى السيد"
CNAMES[karim]="كريم حسن"
CNAMES[walkin]="عميل نقدي"

make_sale() {
    # $1=cust_key  $2=paid_amount  $3=lines_json
    local cust="$1"; shift
    local paid_amount="$1"; shift
    local lines="$1"
    local resp
    resp=$(curl -sS -X POST "$API/api/v1/sales/" "${H[@]}" -d "{
        \"branch_id\": \"$BRANCH_ID\",
        \"customer_id\": \"${CIDS[$cust]}\",
        \"paid_amount\": \"$paid_amount\",
        \"lines\": $lines
    }")
    if ! echo "$resp" | grep -q '"data"'; then
        echo "  ✗ sale failed: $resp"
    fi
}
# Cash sale — paid_amount equals total (35000 + 1500 = 36500)
make_sale walkin "36500.00" "[
    {\"product_id\":\"${PIDS[M-IPH15]}\",\"qty\":1,\"unit_price\":\"35000.00\"},
    {\"product_id\":\"${PIDS[A-ANK65]}\",\"qty\":1,\"unit_price\":\"1500.00\"}
]"
# Cash sale (2*150 + 2*120 = 540)
make_sale ahmed "540.00" "[
    {\"product_id\":\"${PIDS[A-USBC1]}\",\"qty\":2,\"unit_price\":\"150.00\"},
    {\"product_id\":\"${PIDS[A-GLASS]}\",\"qty\":2,\"unit_price\":\"120.00\"}
]"
# Credit sale — sara owes 52000
make_sale sara "0" "[
    {\"product_id\":\"${PIDS[M-S24U]}\",\"qty\":1,\"unit_price\":\"52000.00\"}
]"
# Cash sale (13000 + 1200 = 14200)
make_sale mahmoud "14200.00" "[
    {\"product_id\":\"${PIDS[M-A55]}\",\"qty\":1,\"unit_price\":\"13000.00\"},
    {\"product_id\":\"${PIDS[A-BTEB]}\",\"qty\":1,\"unit_price\":\"1200.00\"}
]"
# Credit sale — karim owes 1350
make_sale karim "0" "[
    {\"product_id\":\"${PIDS[S-BIPH13]}\",\"qty\":1,\"unit_price\":\"1200.00\"},
    {\"product_id\":\"${PIDS[A-USBC1]}\",\"qty\":1,\"unit_price\":\"150.00\"}
]"
# Cash sale (5500)
make_sale noha "5500.00" "[
    {\"product_id\":\"${PIDS[M-RD13]}\",\"qty\":1,\"unit_price\":\"5500.00\"}
]"
echo "  ✓ 6 sales (4 cash + 2 credit)"

# --- 6. Expenses ------------------------------------------------------------
say "Recording expenses..."
make_expense() {
    # $1=account_system_key  $2=amount  $3=description
    local key="$1"; shift
    local amt="$1"; shift
    local desc="$1"
    local resp
    resp=$(curl -sS -X POST "$API/api/v1/expenses/" "${H[@]}" -d "{
        \"branch_id\": \"$BRANCH_ID\",
        \"expense_account_key\": \"$key\",
        \"amount\": \"$amt\",
        \"description\": \"$desc\"
    }")
    if ! echo "$resp" | grep -q '"data"'; then
        echo "  ✗ expense failed: $resp"
    fi
}
make_expense RENT       8000  "إيجار المحل لشهر مايو"
make_expense UTILITIES  1200  "فاتورة كهرباء"
make_expense UTILITIES  450   "اشتراك إنترنت"
make_expense SALARIES   4500  "راتب الموظف - أحمد"
make_expense OTHER_EXPENSES 350 "قهوة + بضاعة استهلاكية"
echo "  ✓ 5 expenses"

# --- 7. Repairs -------------------------------------------------------------
say "Opening repair tickets..."
make_repair() {
    # $1=cust_key  $2=device  $3=problem  $4=estimated_cost
    local cust="$1"; shift
    local device="$1"; shift
    local problem="$1"; shift
    local cost="$1"
    local resp
    resp=$(curl -sS -X POST "$API/api/v1/repairs/" "${H[@]}" -d "{
        \"branch_id\": \"$BRANCH_ID\",
        \"customer_id\": \"${CIDS[$cust]}\",
        \"customer_name\": \"${CNAMES[$cust]}\",
        \"device_model\": \"$device\",
        \"problem\": \"$problem\",
        \"estimated_cost\": \"$cost\"
    }")
    if ! echo "$resp" | grep -q '"data"'; then
        echo "  ✗ repair failed: $resp"
    fi
}
make_repair ahmed   "iPhone 12 Pro"  "شاشة مكسورة"             2500
make_repair sara    "Samsung S22"    "بطارية تنفد بسرعة"        800
make_repair karim   "Xiaomi Note 11" "لا يفتح - تحديث برمجي"   500
make_repair mahmoud "iPhone 11"      "زر الهوم لا يعمل"        1200
echo "  ✓ 4 repairs"

# --- 8. Summary -------------------------------------------------------------
say "Demo seed complete!"
echo ""
echo "  URL    : http://72.62.7.12:8080"
echo "  Tenant : $SLUG ($TENANT_NAME)"
echo "  Login  : $ADMIN_USER / $ADMIN_PASS"
echo ""
