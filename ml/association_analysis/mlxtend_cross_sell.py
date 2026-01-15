# -*- coding: utf-8 -*-
"""
Association rule mining using mlxtend based on 'apyori_cross_sell_generated.xlsx'
基于 'apyori_cross_sell_generated.xlsx'，使用 mlxtend 进行关联分析
输出到一个 Excel 文件：一页总览 + 每个产品一页
"""

import pandas as pd  # 用于数据读取与处理 / For data loading and processing
from mlxtend.preprocessing import TransactionEncoder  # 事务编码工具 / To encode transactions
from mlxtend.frequent_patterns import apriori, association_rules  # 频繁项集与关联规则 / Frequent itemsets & rules


# ---------------------------------------------------
# 1. 参数设置 / Parameter settings
# ---------------------------------------------------
input_file = "apyori_cross_sell_generated.xlsx"   # 输入文件名 / Input Excel file name
output_file = "mlxtend_association_result.xlsx"   # 输出结果文件名 / Output Excel file name

min_support = 0.02      # 最小支持度阈值 / Minimum support threshold
min_confidence = 0.2    # 最小置信度（概率）阈值 / Minimum confidence (probability) threshold
min_lift = 1.0          # 最小提升度阈值 / Minimum lift threshold


# ---------------------------------------------------
# 2. 读取 Excel 并转换为“事务列表”格式
#    Load Excel and convert to transaction list
# ---------------------------------------------------
# 读取原始 Excel 数据 / Read original Excel data
df = pd.read_excel(input_file)

# 假设商品列命名为 Item_1, Item_2, ...，先筛选出这些列
# Assume item columns are named Item_1, Item_2, ...; filter them
item_cols = [col for col in df.columns if col.startswith("Item_")]

# 将每一行转换为一个“购物篮列表”，例如 ["Product1", "Product2"]
# Convert each row into a "basket list", e.g., ["Product1", "Product2"]
transactions = []
for _, row in df.iterrows():
    # 取出该行所有非空且非空字符串的商品 / Take non-empty items in this row
    basket = [
        str(row[col]).strip()
        for col in item_cols
        if pd.notna(row[col]) and str(row[col]).strip() != ""
    ]
    if basket:  # 确保该事务非空 / Ensure transaction is not empty
        transactions.append(basket)

# 提取所有出现过的产品，方便后面按产品建表 / Extract all unique products for later per-product sheets
all_products = sorted({item for t in transactions for item in t})


# ---------------------------------------------------
# 3. 使用 TransactionEncoder 转为 One-Hot 编码
#    Use TransactionEncoder to one-hot encode the data
# ---------------------------------------------------
te = TransactionEncoder()  # 创建事务编码器 / Create transaction encoder
te_array = te.fit(transactions).transform(transactions)  # 进行编码 / Fit and transform

# 将编码后的布尔矩阵转换为 DataFrame，列为各产品名，值为 True/False
# Convert the encoded boolean array to DataFrame, columns are product names
df_onehot = pd.DataFrame(te_array, columns=te.columns_)


# ---------------------------------------------------
# 4. 使用 mlxtend.apriori 找出频繁项集
#    Use mlxtend.apriori to find frequent itemsets
# ---------------------------------------------------
frequent_itemsets = apriori(
    df_onehot,
    min_support=min_support,  # 支持度阈值 / Support threshold
    use_colnames=True         # 直接使用产品名而不是列索引 / Use item names (not column indices)
)

# 如果没有频繁项集，则直接提示并结束 / If no frequent itemsets, print message and exit
if frequent_itemsets.empty:
    print("No frequent itemsets found. Try lowering min_support.")
    # exit(0)


# ---------------------------------------------------
# 5. 基于频繁项集生成关联规则
#    Generate association rules from frequent itemsets
# ---------------------------------------------------
rules_df = association_rules(
    frequent_itemsets,
    metric="confidence",       # 以置信度作为筛选指标 / Use confidence as the metric
    min_threshold=min_confidence  # 最小置信度阈值 / Minimum confidence
)

# 再根据提升度过滤规则（可选）/ Further filter rules by lift (optional)
rules_df = rules_df[rules_df["lift"] >= min_lift].copy()

# 如果规则为空，同样提示 / If no rules after filtering
if rules_df.empty:
    print("No association rules found after filtering by confidence and lift.")
    # exit(0)


# ---------------------------------------------------
# 6. 整理输出字段：前件、后件转为字符串形式
#    Clean up columns: convert antecedents & consequents to string
# ---------------------------------------------------
def frozenset_to_sorted_str(fs):
    """将 frozenset 转为按字母排序的逗号分隔字符串
    Convert a frozenset to a sorted comma-separated string
    """
    return ", ".join(sorted(list(fs)))

# 新建展示友好的列 / Create user-friendly columns
rules_df["Base_Product"] = rules_df["antecedents"].apply(frozenset_to_sorted_str)
rules_df["Associated_Product"] = rules_df["consequents"].apply(frozenset_to_sorted_str)

# 只保留我们关心的列：前件、后件、支持度、置信度、提升度
# Keep only relevant columns for output
result_df = rules_df[[
    "Base_Product",
    "Associated_Product",
    "support",
    "confidence",
    "lift"
]].copy()

# 为列重命名，使含义更清晰 / Rename columns for clarity
result_df.rename(columns={
    "support": "Support",          # 支持度
    "confidence": "Confidence",    # 置信度（概率）
    "lift": "Lift"                 # 提升度
}, inplace=True)


# ---------------------------------------------------
# 7. 写入 Excel：一页总览 + 每个产品一页
#    Write to Excel: one overview sheet + one sheet per product
# ---------------------------------------------------
with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    # 7.1 写入总览页：所有规则
    #     Write overview sheet: all association rules
    result_df.to_excel(writer, sheet_name="All_Associations", index=False)

    # 7.2 为每一个产品单独生成一个 Sheet
    #     For each product, create one dedicated sheet
    for product in all_products:
        # 选出该产品出现在前件中的所有规则
        # Select rules where the product appears in the antecedent (Base_Product)
        product_rules = result_df[result_df["Base_Product"].str.contains(
            rf"\b{product}\b"
        )].copy()

        # 如果没有规则，也写一个空表，便于统一展示
        # If no rules for this product, write an empty sheet with headers
        if product_rules.empty:
            empty_df = pd.DataFrame(columns=result_df.columns)
            empty_df.to_excel(writer, sheet_name=product, index=False)
        else:
            product_rules.to_excel(writer, sheet_name=product, index=False)

print(f"Association rules saved to: {output_file}")
print("关联规则已成功写入 Excel 文件。")
