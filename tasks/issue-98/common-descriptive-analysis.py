import pandas as pd
import numpy as np


# =========================
# 1. 读取数据
# =========================

file_path = "cleaned_data.xlsx"
df = pd.read_excel(file_path)

output_file = "描述性统计分析报告.xlsx"


# =========================
# 2. 数据基本情况
# =========================

basic_info = pd.DataFrame({
    "项目": [
        "样本数",
        "字段数",
        "重复行数量"
    ],
    "结果": [
        df.shape[0],
        df.shape[1],
        df.duplicated().sum()
    ]
})


# =========================
# 3. 字段类型统计
# =========================

field_info = pd.DataFrame({
    "字段名": df.columns,
    "数据类型": [str(df[col].dtype) for col in df.columns],
    "非空数量": [df[col].notna().sum() for col in df.columns],
    "缺失数量": [df[col].isna().sum() for col in df.columns],
    "缺失比例": [(df[col].isna().mean() * 100).round(2) for col in df.columns],
    "唯一值数量": [df[col].nunique(dropna=True) for col in df.columns]
})


# =========================
# 4. 自动识别字段类型
# =========================

numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()

datetime_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64"]).columns.tolist()

non_numeric_cols = df.select_dtypes(
    exclude=["int64", "float64", "datetime64[ns]", "datetime64"]
).columns.tolist()


# 识别 0/1 型字段
binary_cols = []

for col in df.columns:
    values = set(df[col].dropna().unique())
    if values.issubset({0, 1}) and len(values) <= 2:
        binary_cols.append(col)


# 从数值字段中剔除 0/1 型字段
continuous_numeric_cols = [
    col for col in numeric_cols
    if col not in binary_cols
]


field_type_summary = pd.DataFrame({
    "字段类型": [
        "连续数值型字段",
        "0/1二元字段",
        "非数值型字段",
        "日期时间字段"
    ],
    "字段数量": [
        len(continuous_numeric_cols),
        len(binary_cols),
        len(non_numeric_cols),
        len(datetime_cols)
    ],
    "字段列表": [
        "、".join(continuous_numeric_cols),
        "、".join(binary_cols),
        "、".join(non_numeric_cols),
        "、".join(datetime_cols)
    ]
})


# =========================
# 5. 数值型字段描述性统计
# =========================

if len(continuous_numeric_cols) > 0:
    numeric_desc = df[continuous_numeric_cols].describe().T

    numeric_desc["中位数"] = df[continuous_numeric_cols].median()
    numeric_desc["众数"] = [
        df[col].mode().iloc[0] if not df[col].mode().empty else np.nan
        for col in continuous_numeric_cols
    ]
    numeric_desc["偏度"] = df[continuous_numeric_cols].skew()
    numeric_desc["峰度"] = df[continuous_numeric_cols].kurtosis()
    numeric_desc["变异系数"] = (
        df[continuous_numeric_cols].std() / df[continuous_numeric_cols].mean()
    )

    numeric_desc = numeric_desc.rename(columns={
        "count": "样本数",
        "mean": "均值",
        "std": "标准差",
        "min": "最小值",
        "25%": "下四分位数",
        "50%": "中位数_describe",
        "75%": "上四分位数",
        "max": "最大值"
    })

    numeric_desc = numeric_desc.round(4)
else:
    numeric_desc = pd.DataFrame()


# =========================
# 6. 0/1 二元字段统计
# =========================

binary_summary_list = []

for col in binary_cols:
    value_counts = df[col].value_counts(dropna=False)
    value_ratio = df[col].value_counts(normalize=True, dropna=False)

    temp = pd.DataFrame({
        "字段名": col,
        "取值": value_counts.index,
        "数量": value_counts.values,
        "比例": (value_ratio.values * 100).round(2)
    })

    binary_summary_list.append(temp)

if len(binary_summary_list) > 0:
    binary_summary = pd.concat(binary_summary_list, ignore_index=True)
else:
    binary_summary = pd.DataFrame(columns=["字段名", "取值", "数量", "比例"])


# =========================
# 7. 非数值型字段频数统计
# =========================

category_summary_list = []

for col in non_numeric_cols:
    value_counts = df[col].value_counts(dropna=False)
    value_ratio = df[col].value_counts(normalize=True, dropna=False)

    temp = pd.DataFrame({
        "字段名": col,
        "取值": value_counts.index.astype(str),
        "数量": value_counts.values,
        "比例": (value_ratio.values * 100).round(2)
    })

    category_summary_list.append(temp)

if len(category_summary_list) > 0:
    category_summary = pd.concat(category_summary_list, ignore_index=True)
else:
    category_summary = pd.DataFrame(columns=["字段名", "取值", "数量", "比例"])


# =========================
# 8. 非数值型字段概览
# =========================

category_overview_list = []

for col in non_numeric_cols:
    top_value = df[col].mode().iloc[0] if not df[col].mode().empty else np.nan
    top_count = df[col].value_counts(dropna=False).iloc[0] if df[col].value_counts(dropna=False).shape[0] > 0 else 0
    top_ratio = top_count / len(df) * 100 if len(df) > 0 else 0

    category_overview_list.append({
        "字段名": col,
        "类别数量": df[col].nunique(dropna=True),
        "出现最多的类别": top_value,
        "出现最多类别的数量": top_count,
        "出现最多类别的比例": round(top_ratio, 2)
    })

category_overview = pd.DataFrame(category_overview_list)


# =========================
# 9. 日期时间字段统计
# =========================

datetime_summary_list = []

for col in datetime_cols:
    datetime_summary_list.append({
        "字段名": col,
        "最早时间": df[col].min(),
        "最晚时间": df[col].max(),
        "时间跨度_天": (df[col].max() - df[col].min()).days
        if pd.notna(df[col].max()) and pd.notna(df[col].min())
        else np.nan
    })

datetime_summary = pd.DataFrame(datetime_summary_list)


# =========================
# 10. 数值字段相关性分析
# =========================

if len(continuous_numeric_cols) >= 2:
    corr_matrix = df[continuous_numeric_cols].corr().round(4)
else:
    corr_matrix = pd.DataFrame()


# =========================
# 11. 如果有“价格”“金额”“销售额”等目标字段，自动做分组统计
# =========================

possible_target_keywords = ["价格", "金额", "销售额", "收入", "成本", "利润", "销量", "数量"]
target_cols = []

for col in continuous_numeric_cols:
    if any(keyword in col for keyword in possible_target_keywords):
        target_cols.append(col)

group_stats_list = []

for target_col in target_cols:
    for group_col in non_numeric_cols + binary_cols:
        if group_col in df.columns:
            group_stats = df.groupby(group_col)[target_col].agg(
                样本数="count",
                均值="mean",
                中位数="median",
                标准差="std",
                最小值="min",
                最大值="max"
            ).reset_index()

            group_stats.insert(0, "目标字段", target_col)
            group_stats.insert(1, "分组字段", group_col)

            group_stats_list.append(group_stats)

if len(group_stats_list) > 0:
    group_stats_all = pd.concat(group_stats_list, ignore_index=True)
    group_stats_all = group_stats_all.round(4)
else:
    group_stats_all = pd.DataFrame()


# =========================
# 12. 导出 Excel 报告
# =========================

with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    basic_info.to_excel(writer, sheet_name="基本信息", index=False)
    field_info.to_excel(writer, sheet_name="字段信息", index=False)
    field_type_summary.to_excel(writer, sheet_name="字段类型汇总", index=False)

    if not numeric_desc.empty:
        numeric_desc.to_excel(writer, sheet_name="数值字段描述统计")

    if not binary_summary.empty:
        binary_summary.to_excel(writer, sheet_name="二元字段频数统计", index=False)

    if not category_overview.empty:
        category_overview.to_excel(writer, sheet_name="非数值字段概览", index=False)

    if not category_summary.empty:
        category_summary.to_excel(writer, sheet_name="非数值字段频数统计", index=False)

    if not datetime_summary.empty:
        datetime_summary.to_excel(writer, sheet_name="日期字段统计", index=False)

    if not corr_matrix.empty:
        corr_matrix.to_excel(writer, sheet_name="相关性矩阵")

    if not group_stats_all.empty:
        group_stats_all.to_excel(writer, sheet_name="目标字段分组统计", index=False)


# =========================
# 13. 控制台输出简要结果
# =========================

print("=" * 60)
print("描述性统计分析完成")
print("=" * 60)

print("\n一、数据基本情况")
print(basic_info)

print("\n二、字段类型汇总")
print(field_type_summary)

print("\n三、数值型字段")
print(continuous_numeric_cols)

print("\n四、0/1二元字段")
print(binary_cols)

print("\n五、非数值型字段")
print(non_numeric_cols)

print("\n六、日期时间字段")
print(datetime_cols)

print(f"\n报告已保存为：{output_file}")