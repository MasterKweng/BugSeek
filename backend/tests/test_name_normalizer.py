from app.utils.name_normalizer import normalize_name


def test_normalize_name_purchase_orders():
    assert normalize_name("t_purchase_orders") == "purchase_order"


def test_normalize_name_sys_users():
    assert normalize_name("sys_users") == "user"


def test_normalize_name_orders():
    assert normalize_name("orders") == "order"


def test_normalize_name_order_singular_unchanged():
    assert normalize_name("order") == "order"


def test_normalize_name_uppercase_and_prefix():
    assert normalize_name("ERP_Orders") == "order"


def test_normalize_name_multi_tokens():
    assert normalize_name("t_order_items") == "order_item"
