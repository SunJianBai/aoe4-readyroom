# AoE4 World 文明胜率接入调研（2026-10-19）

范围：仅研究公开统计及拟迁入本工具箱的边界；未修改应用代码。以下将官方文档、实际响应和产品建议分开。

## 官方已确认

- [官方 API 文档](https://aoe4world.com/api/)列出 `GET /api/v0/stats/rm_solo/matchups`（文明对阵矩阵）和 `GET /api/v0/stats/rm_solo/civilizations`（文明总览）。两者支持 `patch`、`rank_level`、`rating` 筛选；文档没有要求这两个统计接口提供 API key。另有排位 1v1 的 [`/maps`](https://aoe4world.com/api/) 及 `/maps/:map_id`，但 `include_civs=true` 被官方标为开销较大，只应在确需各地图文明数据时使用。快速 1v1 也有对应的文明、对阵和地图接口。[来源：统计接口章节](https://aoe4world.com/api/#stats)
- 2026-10-19 以标识为 `AOEvillagerResearch/0.1` 的 User-Agent 各请求一次排位 1v1 两个统计接口，均无需密钥即返回 JSON。对阵响应顶层为 `leaderboard/rank_level/rating/patch/data`，当次有 23×23＝529 行；每行含 `civilization`、`other_civilization`、`win_rate`、`win_count`、`games_count`、`player_games_count`、`duration_median`、`duration_average`。文明总览当次有 23 行，并额外含 `pick_rate`。这是**当日响应观察**，不是保证将来始终有 23 个文明或固定字段的契约。[对阵实例](https://aoe4world.com/api/v0/stats/rm_solo/matchups) · [文明实例](https://aoe4world.com/api/v0/stats/rm_solo/civilizations)
- API 文档中的 `patch` 默认值示例 `10257` 已不能当作“当前版本”常量：当次不传 `patch` 的响应回报 `10604,10884,11214,11308`。应以响应实际 `patch` 和页面当前筛选为准，必要时让用户明确选择版本。[文档](https://aoe4world.com/api/#stats) · [实时实例](https://aoe4world.com/api/v0/stats/rm_solo/matchups)
- [对阵网页](https://aoe4world.com/stats/rm_solo/matchups)区分整体胜率的“排除镜像 / 包含镜像”；[单个对阵详情网页](https://aoe4world.com/stats/rm_solo/matchups/english/french)还展示地图、游戏时长、分段胜率视图。官方 API 文档**没有列出稳定的“指定两个文明 × 地图/时长/分段”接口**；不能假定网页可见的每个视图都有可供第三方依赖的公开 API。已文档化的 `/maps/:map_id` 是地图上的文明统计，不等于指定两文明的地图对阵。[来源：API 统计章节](https://aoe4world.com/api/#stats)
- [官方 FAQ](https://aoe4world.com/faq#statistics)称统计每天 UTC 日终重算，并警告补丁刚发布、筛选范围过窄时样本可能过小，解读前应看场次数。

## 使用边界和未知项

- [官方使用说明](https://aoe4world.com/api/#usage-notes)要求负责任地请求，不做多余调用或通过 API 爬取全部数据；自动化调用不得伪装浏览器 User-Agent，应注明应用及可选联系方式；建议本地缓存，复杂/大量数据需求先通过其 Discord 联系开发者。页面没有公布针对这两个统计接口的具体数字频率上限，不能自行宣称“无限制”。
- 文档没有给出统计数据的明确再分发许可条款；“公开可 GET”不等同于“可将数据永久打包进 EXE 并无限再分发”。若计划离线固化或大规模公开分发，需进一步向站点确认。页面页脚关于微软游戏素材的使用说明也不等于 AoE4 World 统计数据的授权。[API 文档](https://aoe4world.com/api/) · [页面页脚](https://aoe4world.com/stats/rm_solo/matchups/english/french)
- 文明总览与对阵矩阵的“整体胜率”口径可能不同：网页明确区分镜像对局，而 API 行含多种场次计数。建议直接展示原接口 `win_rate`，并注明是否包含镜像，不用未经验证的 `win_count/games_count` 自行重算。响应不含明确的 `updated_at` 字段（当次观察），本地应记录抓取时间；抓取时间不等于站点数据统计时间。

## 建议迁移范围（产品判断，非官方要求）

1. 第一版做独立“文明胜率”子页：默认排位 1v1；文明总览显示胜率、选择率、场次数；进入文明后显示它对各文明的对阵胜率和场次数。控件提供补丁和一个段位/分数筛选，但避免把所有网页选项一次搬进来。两次数据请求即可支撑主要页面，无须为每个格子分别请求。
2. 请求应由用户打开该子页或手动刷新时触发；本地缓存至少到下一次 UTC 日终统计更新，离线时显示上次结果和抓取时间，明确标为“历史快照”。不要把离线开局流程的“永不现场更新”机制自动套到时效性强的胜率上。
3. 高亮样本量不足的格子，默认不按胜率给文明贴“强/弱”结论；提供原站链接和来源标识。手机版/窄窗可采用“选我方文明 → 对手列表”，宽窗再展示完整热力矩阵。
4. 暂不迁移个人玩家/排行榜/赛事/录像、所有队伍模式、对局时间曲线及每个“文明 × 对手 × 地图”详细拆分。这些偏离当前工具箱的开局学习场景，部分缺少已文档化的稳定统计接口，且过多筛选会放大低样本误读和请求量。地图文明胜率可作为后续可选第二阶段，用官方 `/maps/:map_id` 而非昂贵的全地图 `include_civs=true`。

实现前再核对：现行补丁列表/参数格式、各文明 slug 映射、镜像对局口径、错误/限流响应，以及是否允许公开再分发离线快照。以上未验证项目不能以这份笔记代替测试或站点授权。
