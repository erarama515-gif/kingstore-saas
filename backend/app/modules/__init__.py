"""Business modules.

Each module is a bounded context:

    modules/<name>/
        __init__.py
        models.py        # SQLAlchemy ORM
        schemas.py       # Pydantic request/response shapes
        repository.py    # DB access, returns ORM objects
        service.py       # Business rules; the *only* public surface
        routes.py        # Flask blueprint
        events.py        # Domain events emitted/handled

Cross-module dependencies go through ``service.py`` only. Repositories and
models are private to their module.
"""

# Foundation model imports are needed so SQLAlchemy registers them on Base
# before Alembic autogenerate runs. As more modules land, add their imports.
from app.modules.tenants import models as _tenants_models  # noqa: F401
from app.modules.users import models as _users_models  # noqa: F401
from app.modules.branches import models as _branches_models  # noqa: F401
from app.modules.auth import models as _auth_models  # noqa: F401
# customers + suppliers register BEFORE accounting because journal_lines FKs
# reference them.
from app.modules.customers import models as _customers_models  # noqa: F401
from app.modules.suppliers import models as _suppliers_models  # noqa: F401
from app.modules.accounting import models as _accounting_models  # noqa: F401
from app.modules.products import models as _products_models  # noqa: F401
from app.modules.inventory import models as _inventory_models  # noqa: F401
from app.modules.devices import models as _devices_models  # noqa: F401
from app.modules.sales import models as _sales_models  # noqa: F401
from app.modules.expenses import models as _expenses_models  # noqa: F401
from app.modules.treasury import models as _treasury_models  # noqa: F401
from app.modules.repairs import models as _repairs_models  # noqa: F401
