import pandas as pd
import matplotlib.pyplot as plt
import os
print(os.getcwd())  #显示工作目录

# 设置中文，防止乱码
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 输出图片文件夹，如果不存在自动创建
img_out_path = "dashboard/img"
os.makedirs(img_out_path, exist_ok=True)

# 读取原始csv，无表头，手动指定列名
df = pd.read_csv("data/UserBehavior.csv",
                 names=['user_id','item_id','category_id','behavior','timestamp'],
                 dtype={'behavior': 'category',
                        'user_id': 'int32',
                        'item_id': 'int32',
                        'category_id': 'int32'})

# 转换时间
start_ts = int(pd.Timestamp('2017-11-25 00:00:00', tz='Asia/Shanghai').timestamp())
end_ts   = int(pd.Timestamp('2017-12-04 00:00:00', tz='Asia/Shanghai').timestamp())

# 先在整数时间戳上过滤，比转完 datetime 再比快得多（8000万行差别很明显）
df = df[(df['timestamp'] >= start_ts) & (df['timestamp'] < end_ts)]

# 只对过滤后的数据做一次时间转换，并转成北京时间
ts_bj = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Shanghai')
df['dt']   = ts_bj.dt.date
df['hour'] = ts_bj.dt.hour
df = df.drop_duplicates()

# -----1.大盘指标打印到控制台
pv = len(df[df['behavior'] == 'pv'])    # 布尔筛选
fav = len(df[df['behavior'] == 'fav'])
cart = len(df[df['behavior'] == 'cart'])
buy = len(df[df['behavior'] == 'buy'])
print(f"总PV:{pv},收藏:{fav},加购:{cart},下单:{buy}")  # f-string，{}是占位符

# -----2.每日DAU图，保存图片
daily_dau = df.groupby('dt')['user_id'].nunique()   # 按日期分组，统计去重用户数dau
plt.figure(figsize=(10,4))  #创建画布
daily_dau.plot(kind='bar', title='每日DAU')   # 画图，设置图片类型和标题
plt.tight_layout()  # 自动调整布局
plt.savefig(f"{img_out_path}/daily_dau.png")    # 保存文件
plt.close()     # 关闭图片

# -----每日pv趋势
daily_pv = df[df['behavior']=='pv'].groupby('dt').size()
plt.figure(figsize=(10,4))
daily_pv.plot(kind='line', title='每日pv趋势')
plt.tight_layout()
plt.savefig(f"{img_out_path}/daily_pv.png")
plt.close()

# -----3.小时活跃图
daily = (df.groupby(['dt', 'hour'])['user_id']
           .nunique()
           .rename('uv')
           .reset_index())

hourly = (daily.groupby('hour')['uv']
               .agg(avg_uv='mean', max_uv='max', day_cnt='count')
               .reindex(range(24)))

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(hourly.index, hourly['avg_uv'], marker='o', lw=2, label='日均 UV')
ax.plot(hourly.index, hourly['max_uv'], marker='s', lw=1.5, color='#c0504d', label='单日峰值')

ax.set_xticks(range(24))
ax.set_xticklabels([f'{h:02d}' for h in range(24)])
ax.set_xlabel('小时')
ax.set_ylabel('UV')
ax.set_title('24 小时分时段活跃 UV（日均口径）')
ax.grid(alpha=0.3)
ax.legend()
plt.tight_layout()
plt.savefig(f"{img_out_path}/hour_active.png", dpi=150, bbox_inches='tight')
plt.close()

# -----4.转化漏斗（两级主漏斗 + 收藏/加购分支）-----
piv = (df[df['behavior'].isin(['pv', 'fav', 'cart', 'buy'])]
         .loc[:, ['user_id', 'behavior']]
         .drop_duplicates()
         .assign(v=1)
         .pivot_table(index='user_id', columns='behavior',
                      values='v', aggfunc='max', fill_value=0))

pv  = piv['pv'].eq(1)
buy = piv['buy'].eq(1)
fc  = piv['fav'].eq(1) | piv['cart'].eq(1)

n_pv     = int(pv.sum())
n_pv_buy = int((pv & buy).sum())
n_pv_fc  = int((pv & fc).sum())
n_fc_buy = int((pv & fc & buy).sum())
n_direct = int((pv & ~fc & buy).sum())

funnel = pd.DataFrame({'stage': ['浏览', '下单'],
                       'uv':    [n_pv, n_pv_buy]})
funnel['总转化率']   = funnel['uv'] / funnel['uv'].iloc[0]
funnel['环节转化率'] = funnel['uv'] / funnel['uv'].shift(1)
print(funnel.to_string(index=False))
print(f'\n浏览用户中有收藏/加购：{n_pv_fc:,}（{n_pv_fc/n_pv:.1%}），'
      f'其中下单 {n_fc_buy:,}（{n_fc_buy/n_pv_fc:.1%}）')
print(f'未经收藏/加购直接下单：{n_direct:,}（{n_direct/n_pv:.1%}）')

plot_df = funnel.iloc[::-1].reset_index(drop=True)

fig, ax = plt.subplots(figsize=(8, 4))
ax.barh(plot_df['stage'], plot_df['uv'], color='#4f81bd', height=0.5)
for i, row in plot_df.iterrows():
    ax.text(row['uv'], i, f'  {row["uv"]:,}　({row["总转化率"]:.1%})',
            va='center', fontsize=10)

ax.set_xlim(0, n_pv * 1.25)
ax.set_xlabel('UV')
ax.set_title('用户转化漏斗：浏览 → 下单')
ax.grid(axis='x', alpha=0.3)
ax.set_axisbelow(True)
plt.tight_layout()
plt.savefig(f"{img_out_path}/funnel.png", dpi=150, bbox_inches='tight')
plt.close()

funnel.to_csv(f"{img_out_path}/funnel.csv", index=False)

# -----5.类目浏览量和转化统计
cat_pv = df[df['behavior']=='pv'].groupby('category_id').size().rename('cat_pv')
cat_buy_uv = df[df['behavior']=='buy'].groupby('category_id')['user_id'].nunique().rename('cat_buy_uv')
cat_stats = pd.merge(cat_pv, cat_buy_uv, on='category_id')
cat_top20 = cat_stats.sort_values('cat_pv',ascending=False).head(20)
print('\n---类目浏览量和转化统计top20---')
print(cat_top20)
cat_top20.to_csv(f"{img_out_path}/cat_top20.csv", index=False, encoding='utf_8_sig')

# -----6.Cohort留存计算，打印控制台并输出csv
first_dt = df.groupby('user_id')['dt'].min().rename('first_dt').reset_index()   # 按user_id分组，求每一组的最小dt，重命名为first_dt，索引user_id设置为列名
visit = df[['user_id','dt']].drop_duplicates()
cohort = pd.merge(visit, first_dt, on='user_id')    # 合并visit和first_dt两个表
cohort['day_diff'] = (pd.to_datetime(cohort['dt']) - pd.to_datetime(cohort['first_dt'])).dt.days    # 日期相减，取天数
cohort_table = cohort.groupby(['first_dt','day_diff'])['user_id'].nunique().unstack()   #按first_dt,day_diff分组，对用户去重计数，内层索引拆成列名
retention = cohort_table.div(cohort_table[0], axis=0)
retention.to_csv(f"{img_out_path}/retention.csv",encoding='utf_8_sig')
print("\n---Cohort同期群留存率---")
print(retention)