# -*- coding: utf-8 -*-
# 基于 DBSCAN 对客户进行聚类，并将结果输出到 Excel
# Use DBSCAN to cluster customers and export results to an Excel file

import pandas as pd  # 导入 pandas 处理表格数据 / Import pandas for table data processing
from sklearn.cluster import DBSCAN  # 导入 DBSCAN 聚类算法 / Import DBSCAN clustering algorithm
from sklearn.preprocessing import StandardScaler  # 导入标准化工具 / Import StandardScaler for normalization

# ========= 参数设置（可根据需要修改） / Parameter settings (can be modified) =========
input_file = "Stock Customer.xlsx"           # 输入的原始客户数据文件 / Input original customer data file
output_file = "Stock_Customer_DBSCAN.xlsx"   # 输出结果文件名 / Output result file name

# DBSCAN 关键参数（可调整以改变聚类效果）
# Key parameters for DBSCAN (you can tune them to change clustering effect)
eps = 0.5          # 邻域半径，数值越大，每个点的“邻居”越多 / Neighborhood radius; larger value means more neighbors per point
min_samples = 5    # 一个点成为核心点所需的最少邻居数量 / Minimum number of neighbors for a point to be a core point

# ========= 第一步：读取数据 / Step 1: Read data =========
df = pd.read_excel(input_file)  # 读取 Excel 文件为 DataFrame / Read Excel file as a DataFrame

# ========= 第二步：选择用于聚类的数值型字段 / Step 2: Select numeric features for clustering =========
# 只保留数值型列（int、float 等），非数值列自动忽略
# Keep only numeric columns (int, float, etc.), automatically ignore non-numeric columns
numeric_df = df.select_dtypes(include=["int64", "float64", "int32", "float32", "int", "float"])

# 如果你想排除某些字段（如“客户编号”），可以使用下面代码（按需取消注释）
# If you want to exclude some fields (e.g. "CustomerID"), uncomment the line below and modify
# numeric_df = numeric_df.drop(columns=["CustomerID"], errors="ignore")

# 如果完全没有数值型列，则提示错误
# If there are no numeric columns at all, raise an error
if numeric_df.shape[1] == 0:
    raise ValueError("没有找到可用于聚类的数值型字段，请检查数据。"
                     " No numeric columns found for clustering, please check the data.")

# ========= 第三步：缺失值处理与标准化 / Step 3: Handle missing values and normalization =========
# 用各列平均值填补缺失值，避免 DBSCAN 出错
# Fill missing values with column means to avoid DBSCAN errors
numeric_df_filled = numeric_df.fillna(numeric_df.mean())

# 使用标准化将各列缩放到相近的尺度（均值为 0，方差为 1）
# Use standardization to scale columns to similar ranges (mean 0, variance 1)
scaler = StandardScaler()                  # 创建标准化对象 / Create StandardScaler object
X_scaled = scaler.fit_transform(numeric_df_filled)  # 拟合并转换数据 / Fit and transform the data

# ========= 第四步：DBSCAN 聚类 / Step 4: DBSCAN clustering =========
dbscan = DBSCAN(
    eps=eps,             # 邻域半径 / Neighborhood radius
    min_samples=min_samples  # 最少样本数 / Minimum number of samples
)

# 使用标准化后的数据进行聚类，得到每个样本的标签
# Fit DBSCAN on scaled data and get labels for each sample
labels = dbscan.fit_predict(X_scaled)  # 标签可能为 -1（噪声）、0、1、2,... / Labels may be -1 (noise), 0, 1, 2, ...

# ========= 第五步：整理聚类标签，映射为连续的 Cluster_ID / Step 5: Map labels to continuous Cluster_ID =========
# DBSCAN 原始标签中，-1 代表噪声，其余为不同的簇
# In DBSCAN original labels, -1 means noise, others are clusters

unique_labels = sorted(set(labels))  # 唯一标签集合 / Unique label set

# 建立从原始标签 -> 连续 Cluster_ID（1,2,3,...）的映射，噪声保留为 -1
# Build mapping from raw labels -> continuous Cluster_ID (1,2,3,...), keep noise as -1
cluster_id_map = {}
current_id = 1
for lab in unique_labels:
    if lab == -1:
        continue  # 噪声不映射为正整数 / Do not map noise into positive integers
    cluster_id_map[lab] = current_id
    current_id += 1

# 将原始标签转换为 Cluster_ID（1,2,3,...），噪声为 -1
# Convert raw labels to Cluster_ID (1,2,3,...) and keep noise as -1
cluster_ids = [cluster_id_map.get(lab, -1) for lab in labels]

# 把 Cluster_ID 加回原始数据表，便于查看每个客户属于哪一类
# Add Cluster_ID back to original DataFrame so we can see which cluster each customer belongs to
df["Cluster_ID"] = cluster_ids

# 计算实际簇的数量（不包括噪声）
# Compute the number of real clusters (excluding noise)
num_clusters = len([cid for cid in set(cluster_ids) if cid != -1])

# ========= 第六步：统计宏观信息 / Step 6: Summarize macro information =========
summary_rows = []  # 用列表收集每一行汇总信息 / Collect summary rows in a list

# 对每个非噪声簇，统计人数
# For each non-noise cluster, count number of customers
for cid in sorted([c for c in set(cluster_ids) if c != -1]):
    count = (df["Cluster_ID"] == cid).sum()  # 统计该类人数 / Count number of customers in this cluster
    summary_rows.append({
        "Cluster_ID": cid,                   # 聚类编号 / Cluster ID
        "Cluster_Name": f"Cluster_{cid}",    # 聚类名称 / Cluster name
        "Customer_Count": count              # 该类人数 / Number of customers in this cluster
    })

# 单独统计噪声点（Cluster_ID = -1），如果存在
# Separately count noise points (Cluster_ID = -1), if any
noise_count = (df["Cluster_ID"] == -1).sum()
if noise_count > 0:
    summary_rows.append({
        "Cluster_ID": -1,
        "Cluster_Name": "Noise",            # 噪声类名称 / Noise class name
        "Customer_Count": noise_count       # 噪声点数量 / Number of noise samples
    })

# 生成宏观信息 DataFrame
# Create macro summary DataFrame
summary_df = pd.DataFrame(summary_rows)

# 增加总类数信息（不含噪声）
# Add total number of clusters information (excluding noise)
summary_df.loc[len(summary_df)] = {
    "Cluster_ID": "Total_Clusters",   # 总类数 / Total number of clusters
    "Cluster_Name": "",               # 可留空 / Can be left blank
    "Customer_Count": num_clusters    # 真实簇数量（不含噪声）/ Number of real clusters (excluding noise)
}

# ========= 第七步：写入 Excel 文件 / Step 7: Write results to Excel file =========
# 使用 ExcelWriter 在一个工作簿中写入多个工作表
# Use ExcelWriter to write multiple sheets in one workbook
with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    # 1）宏观信息：Summary 工作表
    # 1) Macro information: 'Summary' sheet
    summary_df.to_excel(writer, sheet_name="Summary", index=False)

    # 2）每个簇单独一个工作表：Cluster_1, Cluster_2, ...
    # 2) Each cluster in its own sheet: Cluster_1, Cluster_2, ...
    for cid in sorted([c for c in set(cluster_ids) if c != -1]):
        cluster_data = df[df["Cluster_ID"] == cid]  # 选出该类所有客户 / Select all customers in this cluster
        sheet_name = f"Cluster_{cid}"              # 工作表名称 / Sheet name
        cluster_data.to_excel(writer, sheet_name=sheet_name, index=False)  # 写入 Excel / Write to Excel

    # 3）如果存在噪声点，则单独写一个 Noise 工作表
    # 3) If noise points exist, write them into a 'Noise' sheet
    if noise_count > 0:
        noise_data = df[df["Cluster_ID"] == -1]         # 所有噪声点 / All noise samples
        noise_data.to_excel(writer, sheet_name="Noise", index=False)  # 写入 Excel / Write to Excel

# 输出提示信息
# Print completion message
print("DBSCAN 聚类完成。")
print("实际簇数量（不含噪声）：", num_clusters)
print("结果已保存到：", output_file)
print("DBSCAN clustering finished.")
print("Number of clusters (excluding noise):", num_clusters)
print("Results saved to:", output_file)
