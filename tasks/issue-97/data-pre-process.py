import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler


# =========================
# 1. 读取数据
# =========================

file_path = "产品定价模型.xlsx"
df = pd.read_excel(file_path)

print("数据维度：", df.shape)
print("\n字段类型：")
print(df.dtypes)
print("\n缺失值统计：")
print(df.isnull().sum())
print("\n重复行数量：", df.duplicated().sum())


# =========================
# 2. 字段名称清洗
# =========================

df.columns = df.columns.str.strip()
df.columns = df.columns.str.replace(" ", "_")
df.columns = df.columns.str.replace("（", "_", regex=False)
df.columns = df.columns.str.replace("）", "", regex=False)
df.columns = df.columns.str.replace("(", "_", regex=False)
df.columns = df.columns.str.replace(")", "", regex=False)


# =========================
# 3. 删除重复值
# =========================

df = df.drop_duplicates()


# =========================
# 4. 删除高缺失字段
# =========================

threshold = 0.5
missing_ratio = df.isnull().mean()
cols_to_drop = missing_ratio[missing_ratio > threshold].index
df = df.drop(columns=cols_to_drop)

print("\n删除的高缺失字段：", list(cols_to_drop))


# =========================
# 5. 数值型字段缺失值填充
# =========================

numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns

for col in numeric_cols:
    df[col] = df[col].fillna(df[col].median())


# =========================
# 6. 分类型字段缺失值填充
# =========================

category_cols = df.select_dtypes(include=["object"]).columns

for col in category_cols:
    df[col] = df[col].fillna("未知")


# =========================
# 7. 文本字段清洗
# =========================

text_cols = df.select_dtypes(include=["object"]).columns

for col in text_cols:
    df[col] = df[col].astype(str)
    df[col] = df[col].str.strip()
    df[col] = df[col].str.replace("\n", "", regex=False)
    df[col] = df[col].str.replace("\r", "", regex=False)


# =========================
# 8. 异常值处理：IQR 方法
# =========================

def handle_outliers_iqr(data, cols):
    for col in cols:
        Q1 = data[col].quantile(0.25)
        Q3 = data[col].quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        data[col] = np.where(data[col] < lower_bound, lower_bound, data[col])
        data[col] = np.where(data[col] > upper_bound, upper_bound, data[col])

    return data


numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns
df = handle_outliers_iqr(df, numeric_cols)


# =========================
# 9. 自动识别日期字段：谨慎转换版
# =========================

date_keywords = ["date", "time", "日期", "时间"]
date_cols = []
date_threshold = 0.8

for col in df.columns:
    col_name = str(col).lower()

    # 1. 只有列名包含日期/时间关键词，才进入判断
    if any(keyword in col_name for keyword in date_keywords):

        # 2. 如果该列是普通数值型字段，直接跳过
        if pd.api.types.is_numeric_dtype(df[col]):
            print(f"\n跳过字段：{col}，原因：该列是数值型字段，不作为日期处理")
            continue

        # 3. 尝试转换为日期，但先不覆盖原字段
        converted = pd.to_datetime(df[col], errors="coerce")

        # 4. 计算非空数据数量
        non_null_count = df[col].notna().sum()

        # 5. 判断转换成功且年份合理
        valid_mask = (
            converted.notna()
            & (converted.dt.year >= 1900)
            & (converted.dt.year <= 2100)
        )

        valid_ratio = valid_mask.sum() / non_null_count if non_null_count > 0 else 0

        # 6. 只有有效日期比例达到阈值，才真正转换
        if valid_ratio >= date_threshold:
            df[col] = converted
            date_cols.append(col)
            print(f"已转换为日期字段：{col}，有效日期比例：{valid_ratio:.2%}")
        else:
            print(f"跳过字段：{col}，原因：有效日期比例过低，仅为 {valid_ratio:.2%}")

print("日期字段处理完成。")
print("识别到的日期字段：", date_cols)


# =========================
# 10. One-Hot 编码
# =========================

cat_cols = df.select_dtypes(include=["object", "category"]).columns
df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=False, dtype=int)


# =========================
# 11. 数值标准化
# =========================

numeric_cols = df_encoded.select_dtypes(include=["int64", "float64"]).columns

df_scaled = df_encoded.copy()

if len(numeric_cols) > 0:
    # scaler = StandardScaler()
    scaler = MinMaxScaler()
    df_scaled[numeric_cols] = scaler.fit_transform(df_scaled[numeric_cols])


# =========================
# 12. 保存结果
# =========================

# cleaned_data.xlsx，完成以下数据预处理：
# 字段名称清洗
# 删除重复值
# 删除高缺失字段
# 数值型字段缺失值填充
# 分类型字段缺失值填充
# 文本字段清洗
# 异常值处理：IQR 方法
# 自动识别日期字段
df.to_excel("cleaned_data.xlsx", index=False)

# cleaned_data_encoded.xlsx除了完成cleaned_data.xlsx的工作，还包括：
# One-Hot 编码
df_encoded.to_excel("cleaned_data_encoded.xlsx", index=False)

# cleaned_data_encoded_scaled.xlsx除了完成cleaned_data_encoded.xlsx的工作，还包括：
# 利用MinMaxScaler()做数值标准化
df_scaled.to_excel("cleaned_data_encoded_scaled.xlsx", index=False)

print("\n数据清洗完成。")
print("已保存：cleaned_data.xlsx")
print("已保存：cleaned_data_encoded.xlsx")
print("已保存：cleaned_data_encoded_scaled.xlsx")
