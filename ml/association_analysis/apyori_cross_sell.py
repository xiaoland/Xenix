# -*- coding: utf-8 -*-
# -----------------------------------------------------------
# Apriori association analysis based on "apyori_cross_sell_generated.xlsx"
# 基于“apyori_cross_sell_generated.xlsx”进行 Apriori 关联分析
# 输出：一个 Excel 文件，包含：
# 1）All_Associations：所有规则在同一页
# 2）每个产品一个 sheet：该产品作为前件时的所有关联规则
# -----------------------------------------------------------

import pandas as pd        # 导入 pandas，用于数据读取与处理 / Import pandas for data loading and processing
from apyori import apriori # 从 apyori 库中导入 apriori 算法 / Import apriori algorithm from apyori

# -----------------------------
# 1. 基本参数设置 / Basic settings
# -----------------------------
input_file = "apyori_cross_sell_generated.xlsx"  # 输入文件名（需与脚本放在同一目录）/ Input Excel file name
output_file = "apyori_association_result.xlsx"   # 输出结果 Excel 文件名 / Output Excel file name

min_support = 0.02      # 最小支持度，可根据样本量调整 / Minimum support threshold
min_confidence = 0.2    # 最小置信度（可以理解为“概率”阈值）/ Minimum confidence (probability) threshold
min_lift = 1.0          # 最小提升度 / Minimum lift
min_length = 2          # 最小项集大小（至少包含 2 个商品）/ Minimum length of itemsets (at least 2 items)

# ----------------------------------------
# 2. 读取数据并转换为交易列表 / Load data and build transactions
# ----------------------------------------
# 读取 Excel 数据 / Read Excel file
df = pd.read_excel(input_file)

# 找出所有商品列（假设列名为 Item_1, Item_2, ...）/ Find all item columns (Item_1, Item_2, ...)
item_cols = [col for col in df.columns if col.startswith("Item_")]

# 将每一行转换为一个“购物篮”列表 / Convert each row into a transaction (basket) list
transactions = []  # 用于存放所有交易 / List to store all transactions

for _, row in df.iterrows():
    # 取出该行中所有非空的商品 / Get all non-empty items in this row
    basket = [
        str(row[col]).strip()
        for col in item_cols
        if pd.notna(row[col]) and str(row[col]).strip() != ""
    ]
    transactions.append(basket)  # 加入交易列表 / Append basket to transactions

# 提取所有出现过的产品名称 / Extract all unique product names
all_products = sorted({item for t in transactions for item in t})

# ----------------------------------------
# 3. 使用 apyori 运行 Apriori 算法 / Run Apriori using apyori
# ----------------------------------------
rules = apriori(
    transactions,
    min_support=min_support,       # 最小支持度 / Minimum support
    min_confidence=min_confidence, # 最小置信度 / Minimum confidence
    min_lift=min_lift,             # 最小提升度 / Minimum lift
    min_length=min_length          # 最小项集长度 / Minimum itemset length
)

# 将生成器转换为列表 / Convert generator to list
rules = list(rules)

# ----------------------------------------
# 4. 解析规则为结构化表格 / Parse rules into a structured DataFrame
# ----------------------------------------
rows = []  # 用于存放每条规则的结构化信息 / List to store structured rule records

for rule in rules:
    support = rule.support  # 该项集的支持度 / Support of the itemset

    # ordered_statistics 中包含不同的前件-后件拆分 / ordered_statistics contains different base -> add splits
    for ordered_stat in rule.ordered_statistics:
        base_items = list(ordered_stat.items_base)  # 前件项集（Base）/ Antecedent itemset (base)
        add_items = list(ordered_stat.items_add)    # 后件项集（Add）/ Consequent itemset (add)

        # 如果前件或后件为空，则跳过 / Skip if base or add is empty
        if not base_items or not add_items:
            continue

        confidence = ordered_stat.confidence  # 置信度（可看作“条件概率”）/ Confidence (conditional probability)
        lift = ordered_stat.lift              # 提升度 / Lift

        # 按字母排序，保证展示整齐 / Sort for neat display
        base_items_sorted = sorted(base_items)
        add_items_sorted = sorted(add_items)

        # 将列表转换为逗号分隔字符串，便于在 Excel 中查看 / Convert list to comma-separated string for Excel
        base_str = ", ".join(base_items_sorted)
        add_str = ", ".join(add_items_sorted)

        rows.append({
            "Base_Product": base_str,           # 前件产品或产品组合 / Base product(s)
            "Associated_Product": add_str,      # 关联的产品或产品组合 / Associated product(s)
            "Support": support,                 # 支持度 / Support
            "Confidence": confidence,           # 置信度（概率）/ Confidence (probability)
            "Lift": lift,                       # 提升度 / Lift
            "Base_Set": base_items_sorted       # 用于后面按产品筛选的原始前件列表 / Raw base list for per-product filtering
        })

# 将所有规则转换为 DataFrame / Convert rules to DataFrame
rules_df = pd.DataFrame(rows)

# 如果没有规则，给出友好提示 / If no rules are generated, print a friendly message
if rules_df.empty:
    print("No association rules found. Please try lowering thresholds.")
    # 没有规则时仍然可以决定是否退出 / You can exit or continue as needed
    # exit(0)


# ----------------------------------------
# 5. 写入 Excel：一页总览 + 每个产品一页 / Write to Excel: overview + one sheet per product
# ----------------------------------------
with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    # 5.1 所有规则在一个 sheet 中展示 / All rules in one sheet
    all_assoc_df = rules_df.drop(columns=["Base_Set"])  # 删除仅用于筛选的 Base_Set 列 / Drop helper column Base_Set
    all_assoc_df.to_excel(writer, sheet_name="All_Associations", index=False)

    # 5.2 每个产品一个 sheet：该产品作为前件时的所有规则
    #     One sheet per product: rules where this product appears in the base
    for product in all_products:
        # 使用 Base_Set 列进行精确包含判断 / Filter by checking membership in Base_Set
        product_rules = rules_df[rules_df["Base_Set"].apply(lambda base: product in base)]

        # 如果该产品没有对应规则，可以选择写一个空表或跳过 / If no rules, you can write an empty sheet or skip
        if product_rules.empty:
            # 写一个只有表头的空表 / Write an empty sheet with headers
            empty_df = pd.DataFrame(columns=["Base_Product", "Associated_Product", "Support", "Confidence", "Lift"])
            empty_df.to_excel(writer, sheet_name=product, index=False)
        else:
            # 删除 Base_Set 辅助列，仅保留展示需要的内容 / Drop helper column for final output
            product_rules_out = product_rules.drop(columns=["Base_Set"])
            product_rules_out.to_excel(writer, sheet_name=product, index=False)

print(f"Association rules saved to: {output_file}")
print("关联规则已写入 Excel 文件。")
