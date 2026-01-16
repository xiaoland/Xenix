# -*- coding: utf-8 -*-
"""
加速版：基于“movie_recommendations.xlsx”的电影推荐（只用欧氏距离）
Faster version: movie recommendation based on "movie_recommendations.xlsx" (Euclidean only)

- 使用欧氏距离相似度 / Use Euclidean similarity
- 仅对评论数（评分次数）大于等于阈值的电影做“基准电影” / Only movies with rating count >= MIN_RATINGS_BASE are base movies
- 候选“推荐电影”也要求达到最小评分数 / Candidate movies must have rating count >= MIN_RATINGS_CAND
- 仅保留相似度高于设置阈值的结果 / Only keep pairs whose similarity >= EUCLIDEAN_THRESHOLD
- 每部电影最多推荐 TOP_K 部，宁缺毋滥 / Up to TOP_K recommendations per base movie, fewer is allowed
- 记录共同评分用户数量 Common_User_Count / Record number of common raters
- 使用 NumPy 向量化加速计算 / Use NumPy vectorization for speed
"""

import pandas as pd
import numpy as np

# ===========================
# 1. 参数设置 / Parameter settings
# ===========================

INPUT_FILE = "movie_recommendations.xlsx"          # 输入 Excel 文件名 / Input Excel file name
OUTPUT_FILE = "movie_recommendations_euclidean_only.xlsx"  # 输出 Excel 文件名 / Output Excel file name

MIN_RATINGS_BASE = 20      # “基准电影”最小评分数 / Min rating count for base movies
MIN_RATINGS_CAND = 20      # “候选电影”最小评分数 / Min rating count for candidate movies

EUCLIDEAN_THRESHOLD = 0.4  # 欧氏距离相似度阈值（0~1，越大越相似）/ Euclidean similarity threshold (0~1)
TOP_K = 5                  # 每部基准电影最多推荐数量 / Max number of recommendations per base movie


# ===========================
# 2. 读取数据并适配列名
#    Read data and adapt to column names
# ===========================

df = pd.read_excel(INPUT_FILE)

# 删除类似 "Unnamed: 0" 的无用索引列（如果有）
# Drop useless "Unnamed: 0" columns (if any)
for col in df.columns:
    if str(col).startswith("Unnamed"):
        df = df.drop(columns=[col])

# 自动识别 用户列 / movie 列 / rating 列
# Auto-detect user column / movie title column / rating column
if "用户编号" in df.columns:
    user_col = "用户编号"
elif "UserID" in df.columns:
    user_col = "UserID"
else:
    raise ValueError("未找到用户编号列（用户编号/UserID）。User ID column not found.")

if "名称" in df.columns:
    movie_col = "名称"
elif "Title" in df.columns:
    movie_col = "Title"
else:
    raise ValueError("未找到电影名称列（名称/Title）。Movie title column not found.")

if "评分" in df.columns:
    rating_col = "评分"
elif "Rating" in df.columns:
    rating_col = "Rating"
else:
    raise ValueError("未找到评分列（评分/Rating）。Rating column not found.")

print("使用列 / Using columns:")
print("  User column :", user_col)
print("  Movie column:", movie_col)
print("  Rating column:", rating_col)


# ===========================
# 3. 构建用户-电影评分矩阵，并转为 NumPy
#    Build user-movie rating matrix and convert to NumPy
# ===========================

# 构建透视表：行 = 用户；列 = 电影；值 = 评分
# Build pivot table: rows = users; cols = movies; values = ratings
rating_pivot = df.pivot_table(
    index=user_col,
    columns=movie_col,
    values=rating_col
)

# 电影名列表 / List of movie titles
movies = rating_pivot.columns.tolist()
n_users, n_movies = rating_pivot.shape
print(f"用户数 / users: {n_users}, 电影数 / movies: {n_movies}")

# 每部电影评分次数 / Rating count per movie
movie_rating_counts = df.groupby(movie_col)[rating_col].count()

# 将评分矩阵转为 NumPy 数组，方便快速计算 / Convert to NumPy array for fast computation
R = rating_pivot.values.astype(float)  # shape: (n_users, n_movies)
notna_mask = ~np.isnan(R)              # True 表示该用户对该电影有评分 / True means there is a rating

# 建立电影名到列索引的映射 / Map movie title to column index
movie_to_idx = {m: i for i, m in enumerate(movies)}

# 选出“基准电影”和“候选电影”的索引集合 / Select indices of base movies and candidate movies
base_movies = [m for m in movies if movie_rating_counts[m] >= MIN_RATINGS_BASE]
cand_movies = [m for m in movies if movie_rating_counts[m] >= MIN_RATINGS_CAND]

base_indices = [movie_to_idx[m] for m in base_movies]
cand_indices = [movie_to_idx[m] for m in cand_movies]

print(f'基准电影数(评分 >= {MIN_RATINGS_BASE}) / base movies: {len(base_indices)}')
print(f'候选电影数(评分 >= {MIN_RATINGS_CAND}) / candidate movies: {len(cand_indices)}')


# ===========================
# 4. 欧氏距离推荐（加速版）
#    Euclidean-based recommendation (fast)
# ===========================

euclidean_rows = []  # 用来保存所有推荐结果的列表 / List to store all recommendation rows

for base_idx in base_indices:
    base_movie = movies[base_idx]                     # 当前基准电影名 / base movie title
    base_count = int(movie_rating_counts[base_movie]) # 当前基准电影的评分次数 / rating count of base movie

    # 该电影的评分向量和非空掩码 / Rating vector and non-null mask for this movie
    base_r = R[:, base_idx]
    base_notna = notna_mask[:, base_idx]

    # 暂存候选电影的相似度结果 / Temporarily store candidate results
    candidates = []

    for cand_idx in cand_indices:
        if cand_idx == base_idx:
            # 不跟自己比 / Skip itself
            continue

        cand_movie = movies[cand_idx]
        cand_r = R[:, cand_idx]
        cand_notna = notna_mask[:, cand_idx]

        # 公共用户掩码：两部电影都被评分的用户 / Common users: both have ratings
        common_mask = base_notna & cand_notna
        common_n = int(common_mask.sum())  # 共同评分用户数 / Number of common raters

        if common_n == 0:
            # 没有共同评分用户，无法计算欧氏距离 / No common raters, cannot compute distance
            continue

        # 差值向量 / Difference vector
        diff = base_r[common_mask] - cand_r[common_mask]

        # 欧氏距离 = √(差值平方和) / Euclidean distance = sqrt(sum(diff^2))
        distance = np.sqrt(np.sum(diff * diff))

        # 将距离转为相似度 / Convert distance to similarity
        similarity = 1.0 / (1.0 + distance)

        # 应用相似度阈值过滤 / Apply similarity threshold
        if similarity >= EUCLIDEAN_THRESHOLD:
            candidates.append((cand_movie, similarity, common_n))

    # 按相似度从大到小排序 / Sort candidates by similarity (descending)
    candidates.sort(key=lambda x: x[1], reverse=True)

    # 取前 TOP_K 个 / Take top K
    for rank, (rec_movie, sim_value, common_n) in enumerate(candidates[:TOP_K], start=1):
        euclidean_rows.append({
            "Base_Movie": base_movie,               # 原始电影 / Base movie
            "Base_Rating_Count": base_count,        # 原始电影评分次数 / Rating count of base movie
            "Rank": rank,                           # 推荐顺位 / Recommendation rank
            "Recommended_Movie": rec_movie,         # 推荐电影 / Recommended movie
            "Similarity_Value": sim_value,          # 欧氏相似度 / Euclidean similarity
            "Common_User_Count": common_n           # 共同评分用户数 / Number of common raters
        })

# 将结果转为 DataFrame / Convert results to DataFrame
df_euclidean = pd.DataFrame(euclidean_rows)


# ===========================
# 5. 写入 Excel（只有一个工作表：Euclidean）
#    Write to Excel (single sheet: Euclidean)
# ===========================

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    df_euclidean.to_excel(writer, sheet_name="Euclidean", index=False)

print("欧氏距离结果行数 / Euclidean result rows:", len(df_euclidean))
print("结果已保存到 / Results saved to:", OUTPUT_FILE)
