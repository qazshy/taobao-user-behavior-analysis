import pandas as pd
import matplotlib.pyplot as plt
import os

# 设置中文，防止乱码
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 输出图片文件夹，如果不存在自动创建
img_out_path = "../dashboard/img"
os.makedirs(img_out_path, exist_ok=True)

# 读取原始csv，无表头，手动指定列名
df = pd.read_csv("../data/UserBehavior.csv",
                 names=['user_id','item_id','category_id','behavior','timestamp'])

# 转换时间
df['dt'] = pd.to_datetime(df['timestamp'], unit='s').dt.date
df['hour'] = pd.to_datetime(df['timestamp'], unit='s').dt.hour

# 过滤时间范围
start = pd.to_datetime("2017-11-25").date()
end = pd.to_datetime("2017-12-03").date()
df = df[(df['dt'] >= start) & (df['dt'] <= end)]
df = df.drop_duplicates()

# ==========1.大盘指标打印到控制台==========
pv = len(df[df['behavior'] == 'pv'])
fav = len(df[df['behavior'] == 'fav'])
cart = len(df[df['behavior'] == 'cart'])
buy = len(df[df['behavior'] == 'buy'])
print(f"总PV:{pv},收藏:{fav},加购:{cart},下单:{buy}")

# ==========2.每日DAU图，保存图片==========
daily_dau = df.groupby('dt')['user_id'].nunique()
plt.figure(figsize=(10,4))
daily_dau.plot(kind='bar', title='每日DAU')
plt.tight_layout()
plt.savefig(f"{img_out_path}/daily_dau.png")
plt.close()

# ==========3.小时活跃图==========
hour_uv = df.groupby('hour')['user_id'].nunique()
plt.figure(figsize=(10,4))
hour_uv.plot(kind='line',title='24小时分时段活跃UV')
plt.tight_layout()
plt.savefig(f"{img_out_path}/hour_active.png")
plt.close()

# ==========4.转化漏斗==========
pv_uv = df[df['behavior']=='pv']['user_id'].nunique()
favcart_uv = df[df['behavior'].isin(['fav','cart'])]['user_id'].nunique()
buy_uv = df[df['behavior']=='buy']['user_id'].nunique()

funnel_df = pd.DataFrame({
    'stage':["浏览","收藏/加购","下单"],
    'uv':[pv_uv,favcart_uv,buy_uv]
})
plt.figure(figsize=(8,4))
plt.bar(funnel_df['stage'],funnel_df['uv'])
plt.title("用户级转化漏斗(UV口径)")
plt.tight_layout()
plt.savefig(f"{img_out_path}/funnel.png")
plt.close()

# ==========5.Cohort留存计算，打印控制台并输出csv==========
first_dt = df.groupby('user_id')['dt'].min().reset_index().rename(columns={'dt':'first_dt'})
visit = df[['user_id','dt']].drop_duplicates()
cohort = pd.merge(visit, first_dt, on='user_id')
cohort['day_diff'] = (pd.to_datetime(cohort['dt']) - pd.to_datetime(cohort['first_dt'])).dt.days
cohort_table = cohort.groupby(['first_dt','day_diff'])['user_id'].nunique().unstack()
print("\n=====Cohort留存表=====")
print(cohort_table)
cohort_table.to_csv(f"{img_out_path}/cohort.csv",encoding='utf_8_sig')
