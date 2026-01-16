# -*- coding: utf-8 -*-
# 使用 KMeans 对客户进行聚类，并把结果写入 Excel
# Use KMeans to cluster customers and write results to an Excel file

import pandas as pd  # 导入 pandas 处理表格数据 / Import pandas for table data processing
from sklearn.cluster import KMeans  # 导入 KMeans 聚类算法 / Import KMeans algorithm
from sklearn.preprocessing import StandardScaler  # 导入标准化工具 / Import StandardScaler for normalization

# ========= 参数设置（可以根据需要修改）/ Parameter settings (you can modify) =========
input_file = "Customer Information.xlsx"      # 原始客户数据文件名 / Original customer data file name
output_file = "Customer_Information_KMeans.xlsx"  # 输出结果文件名 / Output result file name
n_clusters = 4  # 聚成多少类（可修改，例如 3、4、5 等）/ Number of clusters (can be changed, e.g. 3, 4, 5, etc.)

# ========= 第一步：读取数据 / Step 1: Read data =========
df = pd.read_excel(input_file)  # 读取 Excel 文件为 DataFrame / Read Excel file as DataFrame

# ========= 第二步：选择用于聚类的数值型字段 / Step 2: Select numeric features for clustering =========
# 只保留数值型列（int、float 等），非数值列自动忽略
# Keep only numeric columns (int, float, etc.), non-numeric columns are ignored
numeric_df = df.select_dtypes(include=["int64", "float64", "int32", "float32", "int", "float"])

# 如果你想排除某些字段（例如“客户编号”），可以使用下面的代码（按需取消注释）
# If you want to exclude some fields (e.g. "CustomerID"), uncomment and modify the line below
# numeric_df = numeric_df.drop(columns=["CustomerID"], errors="ignore")

# 若完全没有数值列，则抛出错误，提醒检查数据
# If there are no numeric columns at all, raise an error to remind checking the data
if numeric_df.shape[1] == 0:
    raise ValueError("没有找到可用于聚类的数值型字段，请检查数据。"
                     "No numeric columns found for clustering, please check the data.")

# ========= 第三步：缺失值处理与标准化 / Step 3: Handle missing values and normalization =========
# 用各列均值填补缺失值（避免 KMeans 出错）
# Fill missing values with column means (to avoid KMeans failure)
numeric_df_filled = numeric_df.fillna(numeric_df.mean())

# 使用标准化将各列缩放到相近的尺度 / Use standardization to scale columns to similar ranges
scaler = StandardScaler()  # 创建标准化对象 / Create a StandardScaler object
X_scaled = scaler.fit_transform(numeric_df_filled)  # 拟合并转换数据 / Fit and transform the data

# ========= 第四步：KMeans 聚类 / Step 4: KMeans clustering =========
kmeans = KMeans(
    n_clusters=n_clusters,  # 聚类个数 / Number of clusters
    random_state=42,        # 随机种子，保证结果可复现 / Random seed for reproducibility
    n_init=10               # 重新初始化中心次数 / Number of centroid initializations
)

# 使用标准化后的数据进行聚类，并得到每个样本的聚类标签（0,1,2,...）
# Fit KMeans on scaled data and get cluster labels (0,1,2,...)
cluster_labels = kmeans.fit_predict(X_scaled)

# 把聚类结果添加回原始数据表，便于查看每个客户属于哪一类
# Add cluster labels back to original DataFrame to see which cluster each customer belongs to
df["Cluster_ID"] = cluster_labels + 1  # 转为 1,2,3,... 这样的类别编号 / Convert to 1,2,3,... style cluster ID

# ========= 第五步：统计宏观信息 / Step 5: Summarize macro information =========
# 按类别统计每一类有多少人 / Count how many customers in each cluster
cluster_counts = df["Cluster_ID"].value_counts().sort_index()  # 按类别编号排序 / Sort by cluster ID

# 构造宏观信息表：第几类、人数
# Build macro summary table: cluster ID and customer count
summary_df = pd.DataFrame({
    "Cluster_ID": cluster_counts.index,        # 类别编号 / Cluster ID
    "Customer_Count": cluster_counts.values   # 对应人数 / Number of customers
})

# （可选）增加总类数这一行信息
# (Optional) Add total number of clusters as an extra row
summary_df.loc[len(summary_df)] = ["Total_Clusters", n_clusters]

# ========= 第六步：写入 Excel 文件 / Step 6: Write results to Excel file =========
# 使用 ExcelWriter，可以在一个文件中创建多个工作表
# Use ExcelWriter to create multiple sheets in one Excel file
with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    # 宏观信息写在 Summary 工作表中（有多少类、每类多少人）
    # Write macro information to 'Summary' sheet (how many clusters and how many customers per cluster)
    summary_df.to_excel(writer, sheet_name="Summary", index=False)

    # 每一类单独一个工作表，例如 Cluster_1, Cluster_2, ...
    # Each cluster is written to its own sheet, e.g., Cluster_1, Cluster_2, ...
    for cid in sorted(df["Cluster_ID"].unique()):
        cluster_data = df[df["Cluster_ID"] == cid]  # 选出该类的所有客户 / Select all customers in this cluster
        sheet_name = f"Cluster_{cid}"  # 工作表名称 / Sheet name
        cluster_data.to_excel(writer, sheet_name=sheet_name, index=False)  # 写入 Excel / Write to Excel

print("聚类完成，结果已保存到：", output_file)
# Print completion message
print("Clustering finished. Results saved to:", output_file)
