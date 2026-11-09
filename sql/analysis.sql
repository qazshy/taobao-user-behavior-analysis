-- 1. 创建项目专用数据库，名字叫 taobao_project
CREATE DATABASE taobao_project DEFAULT CHARACTER SET utf8mb4;

-- 2. 选中这个数据库，后续所有建表、导入都在这个库里面
USE taobao_project;

-- 3. 现在才可以执行建表语句！！
CREATE TABLE user_behavior (
                               user_id BIGINT,
                               item_id BIGINT,
                               category_id BIGINT,
                               behavior VARCHAR(10),
                               ts BIGINT
);

-- 把UserBehavior.csv数据导入user_behavior

-- 新建清洗表，不用原始表做分析
CREATE TABLE ub_clean AS
SELECT
    user_id,
    item_id,
    category_id,
    behavior,
    FROM_UNIXTIME(ts, '%Y-%m-%d') AS dt,
    FROM_UNIXTIME(ts, '%H') AS hour
FROM user_behavior
WHERE FROM_UNIXTIME(ts,'%Y-%m-%d') BETWEEN '2017-11-25' AND '2017-12-03';


-- 统计行数
select count(*) from ub_clean;

-- 建立索引，加快查询速度
ALTER TABLE ub_clean ADD INDEX idx_user (user_id);
ALTER TABLE ub_clean ADD INDEX idx_dt (dt);

SELECT dt,
       COUNT(*) AS row_cnt,
       COUNT(DISTINCT user_id) AS uv
FROM ub_clean
GROUP BY dt
ORDER BY dt;

-- 1、大盘指标：总PV、UV、收藏数、加购数、下单数
SELECT
    SUM(IF(behavior='pv',1,0)) AS total_pv,
    COUNT(DISTINCT IF(behavior='pv',user_id,NULL)) AS pv_uv,
    SUM(IF(behavior='fav',1,0)) AS total_fav,
    SUM(IF(behavior='cart',1,0)) AS total_cart,
    SUM(IF(behavior='buy',1,0)) AS total_buy,
    COUNT(DISTINCT IF(behavior='buy',user_id,NULL)) AS buy_uv
FROM ub_clean;

-- 2、每日DAU、每日PV趋势
SELECT dt,
       COUNT(DISTINCT user_id) AS dau,
       SUM(IF(behavior='pv',1,0)) AS daily_pv
FROM ub_clean
GROUP BY dt ORDER BY dt;

-- 3、小时活跃度分布（看一天哪个点人多）
WITH d AS (
    SELECT dt, hour, COUNT(DISTINCT user_id) AS uv
    FROM ub_clean
    GROUP BY dt, hour
)
SELECT hour,
       AVG(uv)    AS avg_uv,      -- 典型一天这个点的人数
       MAX(uv)    AS max_uv,      -- 峰值
       COUNT(*)   AS day_cnt      -- 有效天数，防止某小时只有几天有数据
FROM d
GROUP BY hour
ORDER BY hour;

-- 4、转化漏斗（核心）
WITH ub AS (
    -- 一行一个用户：三个 0/1 标记，表示"是否发生过某类行为"
    SELECT user_id,
           MAX(CASE WHEN behavior = 'pv'            THEN 1 ELSE 0 END) AS has_pv,
           MAX(CASE WHEN behavior IN ('fav','cart') THEN 1 ELSE 0 END) AS has_fc,
           MAX(CASE WHEN behavior = 'buy'            THEN 1 ELSE 0 END) AS has_buy
    FROM (SELECT DISTINCT user_id, behavior FROM ub_clean) c
    GROUP BY user_id
),
     agg AS (
         SELECT SUM(has_pv)                                                  AS pv_uv,
                SUM(CASE WHEN has_pv = 1 AND has_buy = 1 THEN 1 ELSE 0 END)  AS buy_uv,
                SUM(CASE WHEN has_pv = 1 AND has_fc  = 1 THEN 1 ELSE 0 END)  AS fc_uv,
                SUM(CASE WHEN has_pv = 1 AND has_fc = 1 AND has_buy = 1
                             THEN 1 ELSE 0 END)                                  AS fc_buy_uv,
                SUM(CASE WHEN has_pv = 1 AND has_fc = 0 AND has_buy = 1
                             THEN 1 ELSE 0 END)                                  AS direct_buy_uv
         FROM ub
     )
SELECT pv_uv,
       buy_uv,
       ROUND(buy_uv * 100 / pv_uv, 2)        AS 浏览到下单_pct,
       fc_uv,
       ROUND(fc_uv * 100 / pv_uv, 2)         AS 收藏加购渗透率_pct,
       fc_buy_uv,
       ROUND(fc_buy_uv * 100 / fc_uv, 2)     AS 收藏加购到下单_pct,
       direct_buy_uv,
       ROUND(direct_buy_uv * 100 / pv_uv, 2) AS 直接下单_pct
FROM agg;


-- 5、类目浏览量&转化统计
SELECT category_id,
       SUM(IF(behavior='pv',1,0)) cat_pv,
       COUNT(DISTINCT CASE WHEN behavior='buy' THEN user_id END) cat_buy_uv
FROM ub_clean
GROUP BY category_id
ORDER BY cat_pv DESC LIMIT 20;

-- 6、同期群Cohort留存SQL
-- 思路：取用户首次访问日期作为注册 cohort，看后续日期是否回来访问
WITH f AS (
    SELECT user_id, MIN(dt) AS first_dt FROM ub_clean GROUP BY user_id
),
     v AS (
         SELECT DISTINCT user_id, dt FROM ub_clean
     ),
     cohort AS (
         SELECT first_dt, COUNT(*) AS cohort_size FROM f GROUP BY first_dt
     )
SELECT
    f.first_dt,
    DATEDIFF(v.dt, f.first_dt) AS day_diff,
    c.cohort_size,
    COUNT(DISTINCT f.user_id) AS returned_users,
    ROUND(COUNT(DISTINCT f.user_id) / c.cohort_size, 4) AS retention_rate
FROM f
         JOIN v ON f.user_id = v.user_id
         JOIN cohort c ON f.first_dt = c.first_dt
WHERE v.dt >= f.first_dt
GROUP BY f.first_dt, DATEDIFF(v.dt, f.first_dt), c.cohort_size
ORDER BY f.first_dt, day_diff;


-- 建立Power BI结果表
USE taobao_project;

CREATE TABLE rpt_overview AS
SELECT SUM(IF(behavior='pv',1,0)) AS total_pv,
       COUNT(DISTINCT IF(behavior='pv',user_id,NULL)) AS pv_uv,
       COUNT(DISTINCT IF(behavior='buy',user_id,NULL)) AS buy_uv,
       SUM(IF(behavior='buy',1,0)) AS total_buy
FROM ub_clean;

CREATE TABLE rpt_daily AS
SELECT dt, COUNT(DISTINCT user_id) AS dau, SUM(IF(behavior='pv',1,0)) AS daily_pv
FROM ub_clean GROUP BY dt ORDER BY dt;

CREATE TABLE rpt_hourly AS
WITH d AS (
    SELECT dt, hour, COUNT(DISTINCT user_id) AS uv
    FROM ub_clean
    GROUP BY dt, hour
)
SELECT hour,
       AVG(uv)    AS avg_uv,      -- 典型一天这个点的人数
       MAX(uv)    AS max_uv,      -- 峰值
       COUNT(*)   AS day_cnt      -- 有效天数，防止某小时只有几天有数据
FROM d
GROUP BY hour
ORDER BY hour;

CREATE TABLE rpt_funnel AS
WITH ub AS (
    SELECT user_id,
           MAX(CASE WHEN behavior = 'pv'            THEN 1 ELSE 0 END) AS has_pv,
           MAX(CASE WHEN behavior IN ('fav','cart') THEN 1 ELSE 0 END) AS has_fc,
           MAX(CASE WHEN behavior = 'buy'            THEN 1 ELSE 0 END) AS has_buy
    FROM (SELECT DISTINCT user_id, behavior FROM ub_clean) c
    GROUP BY user_id
)
SELECT 1 AS stage_order, '浏览' AS stage,
       SUM(has_pv) AS uv
FROM ub
UNION ALL
SELECT 2, '收藏/加购',
       SUM(CASE WHEN has_pv = 1 AND has_fc = 1 THEN 1 ELSE 0 END)
FROM ub
UNION ALL
SELECT 3, '下单',
       SUM(CASE WHEN has_pv = 1 AND has_buy = 1 THEN 1 ELSE 0 END)
FROM ub
ORDER BY stage_order;

-- The total number of locks exceeds the lock table size，rpt_cohort建表超过缓冲区大小，可以直接用查询结果导出csv
CREATE TABLE rpt_cohort AS
WITH f AS (
    SELECT user_id, MIN(dt) AS first_dt FROM ub_clean GROUP BY user_id
),
     v AS (
         SELECT DISTINCT user_id, dt FROM ub_clean
     ),
     cohort AS (
         SELECT first_dt, COUNT(*) AS cohort_size FROM f GROUP BY first_dt
     )
SELECT
    f.first_dt,
    DATEDIFF(v.dt, f.first_dt) AS day_diff,
    c.cohort_size,
    COUNT(DISTINCT f.user_id) AS returned_users,
    ROUND(COUNT(DISTINCT f.user_id) / c.cohort_size, 4) AS retention_rate
FROM f
         JOIN v ON f.user_id = v.user_id
         JOIN cohort c ON f.first_dt = c.first_dt
WHERE v.dt >= f.first_dt
GROUP BY f.first_dt, DATEDIFF(v.dt, f.first_dt), c.cohort_size;
