"""API v1 blueprint registry.

Each business module exposes a sub-blueprint that gets registered here. This
file is the single place where the URL surface of v1 is composed.
"""

from __future__ import annotations

from flask import Blueprint

from app.api.v1.health import health_bp
from app.modules.accounting.routes import accounting_bp
from app.modules.auth.routes import auth_bp
from app.modules.customers.routes import customers_bp
from app.modules.inventory.routes import inventory_bp
from app.modules.capital.routes import capital_bp
from app.modules.expenses.routes import expenses_bp
from app.modules.products.routes import products_bp
from app.modules.repairs.routes import repairs_bp
from app.modules.reports.routes import reports_bp
from app.modules.sales.routes import sales_bp
from app.modules.suppliers.routes import suppliers_bp
from app.modules.treasury.routes import treasury_bp


api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
api_v1_bp.register_blueprint(health_bp)
api_v1_bp.register_blueprint(auth_bp)
api_v1_bp.register_blueprint(accounting_bp)
api_v1_bp.register_blueprint(products_bp)
api_v1_bp.register_blueprint(inventory_bp)
api_v1_bp.register_blueprint(customers_bp)
api_v1_bp.register_blueprint(suppliers_bp)
api_v1_bp.register_blueprint(sales_bp)
api_v1_bp.register_blueprint(expenses_bp)
api_v1_bp.register_blueprint(treasury_bp)
api_v1_bp.register_blueprint(capital_bp)
api_v1_bp.register_blueprint(repairs_bp)
api_v1_bp.register_blueprint(reports_bp)

# Future module registration goes here, e.g.:
#   from app.modules.users.routes import users_bp
#   api_v1_bp.register_blueprint(users_bp)
