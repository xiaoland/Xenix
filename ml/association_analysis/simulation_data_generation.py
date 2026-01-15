import pandas as pd
import random

# -----------------------------
# Configurable Parameters
# 可配置参数（可自由调整）
# -----------------------------
num_products = 10        # Number of products (must be ≥ 10)
                         # 产品数量（必须 ≥ 10）

num_customers = 300      # Number of customer samples
                         # 样本数量（客户数）

min_items_per_basket = 2 # Minimum number of products each customer must buy
                         # 每个客户至少购买多少个产品

max_items_per_basket = 6 # Maximum number of products each customer may buy
                         # 每个客户最多购买多少个产品

random.seed(123)         # Set random seed for reproducibility
                         # 设定随机种子，以便结果可复现


# -------------------------------------
# Generate product list
# 生成产品名称列表 Product1 ~ ProductN
# -------------------------------------
products = [f"Product{i}" for i in range(1, num_products + 1)]

transactions = []


# -----------------------------------------------------
# Generate transactions with specified cross-sell logic
# 根据指定的交叉销售关系生成交易数据
# -----------------------------------------------------
for cust_id in range(1, num_customers + 1):
    r = random.random()
    basket = []

    # -------------------------------------------------
    # Pattern A: Product1, Product2, Product3 cross-sell
    # 模式A：Product1、Product2、Product3 强关联交叉销售
    # -------------------------------------------------
    if r < 0.4 and num_products >= 3:
        basket = ["Product1", "Product2", "Product3"]

        # Occasionally add another product
        # 偶尔加入其他产品
        extra_candidates = [p for p in products if p not in basket]
        if extra_candidates and random.random() < 0.5:
            basket.append(random.choice(extra_candidates))

    # -------------------------------------------------
    # Pattern B: Product3 & Product4 cross-sell
    # 模式B：Product3 与 Product4 强关联
    # -------------------------------------------------
    elif r < 0.65 and num_products >= 4:
        basket = ["Product3", "Product4"]

        # Sometimes link to Product1 or Product2
        # 有时会与 Product1 / Product2 联动
        if "Product1" in products and random.random() < 0.4:
            basket.append("Product1")
        if "Product2" in products and random.random() < 0.4:
            basket.append("Product2")

    # -------------------------------------------------
    # Pattern C: Product8 & Product10 cross-sell
    # 模式C：Product8 与 Product10 强关联
    # -------------------------------------------------
    elif r < 0.85 and num_products >= 10:
        basket = ["Product8", "Product10"]

        # Possibly add 1 more product
        # 可能再加一个其他产品
        extra_candidates = [p for p in products if p not in basket]
        if extra_candidates and random.random() < 0.6:
            basket.append(random.choice(extra_candidates))

    # -------------------------------------------------
    # Pattern D: Random noise
    # 模式D：随机噪声交易
    # -------------------------------------------------
    else:
        basket_size = random.randint(
            min_items_per_basket,
            min(max_items_per_basket, num_products)
        )
        basket = random.sample(products, basket_size)

    # Remove duplicates (safe check)
    # 去除重复产品（安全检查）
    basket = list(dict.fromkeys(basket))

    # Ensure minimum number of items
    # 确保至少购买 min_items_per_basket 个商品
    while len(basket) < min_items_per_basket:
        extra = random.choice(products)
        if extra not in basket:
            basket.append(extra)

    transactions.append((cust_id, basket))


# ---------------------------------------------------
# Convert transactions to table format
# 转换为表格格式：CustomerID + Item1/Item2/...
# ---------------------------------------------------
max_len = max(len(t[1]) for t in transactions)

data = []
for cust_id, basket in transactions:
    row = {"CustomerID": f"C{cust_id:04d}"}  # Format: C0001 / C0002 ...
                                             # 格式化客户编号
    for i in range(max_len):
        row[f"Item_{i+1}"] = basket[i] if i < len(basket) else ""
    data.append(row)

df = pd.DataFrame(data)


# -----------------------------
# Save to Excel
# 保存为 Excel 文件
# -----------------------------
output_file = "apyori_cross_sell_generated.xlsx"
df.to_excel(output_file, index=False)

print(f"File saved as: {output_file}")
