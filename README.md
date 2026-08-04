# China Southern Power Grid Statistics for Home Assistant

南方电网电费数据的 Home Assistant 自定义集成（社区维护版）。

[![Release](https://img.shields.io/github/v/release/benj-tang/china_southern_power_grid_stat)](https://github.com/benj-tang/china_southern_power_grid_stat/releases)
[![Tests](https://github.com/benj-tang/china_southern_power_grid_stat/actions/workflows/test.yml/badge.svg)](https://github.com/benj-tang/china_southern_power_grid_stat/actions/workflows/test.yml)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)

> [!IMPORTANT]
> 本项目不是南方电网官方集成，也不是原项目的官方续作。它保留原项目历史与
> GPL-3.0 许可，并针对当前南网在线接口和新版 Home Assistant 做社区维护。
> 云端接口可能随时变化，请勿把本集成用于计费争议或关键财务判断。

## 维护版改进

- 支持 Home Assistant 2025.12+ 的配置流与 Python 3.14；已在
  Home Assistant 2026.7.4 / Python 3.14.6 实机验证。
- 修复南网当前 Web API 的会话通道、AES 响应解密、余额返回结构和年度分析参数。
- 南网 App、微信、支付宝扫码登录使用 HA 原生进度页，每 2 秒自动轮询；扫码确认
  后自动完成，服务端过期或持续未扫码 5 分钟时自动换码，无需手动提交。
- 首次登录自动导入全部已绑定缴费号。
- 登录态失效时启动 HA 重新认证，并显示去重的持久通知；重新登录后自动清除。
- 请求超时 30 秒；日志会遮蔽手机号、缴费号，不记录密码、令牌或完整 API 响应。

完整变更见 [CHANGELOG.md](CHANGELOG.md)，维护原则与来源见
[MAINTENANCE.md](MAINTENANCE.md)。

## 数据范围

当前可用数据取决于南网所在省份、计费周期和接口实际响应：

- 余额与欠费；
- 本年、上年总用电量和总电费，以及滚动近四年的官方逐月电量/电费明细；
- 本月、上月总用电量和逐日用电量；
- 最新已发布日用电量；
- 当接口提供时显示月电费、逐日电费和阶梯信息。

南网页面说明日用电数据可能在 **T+3 天内**发布，因此“昨日用电”短期为未知是
正常状态。当前网页使用的月度接口在部分账号上不返回月电费、逐日电费和阶梯字段；
本集成会保持 `unavailable`，不会用 0 或本地估算冒充官方数据。年度电费走独立
年度分析接口，不受上述缺失影响。

## 安装

### HACS 自定义仓库

1. 在 HACS 中打开“自定义仓库”。
2. 添加 `https://github.com/benj-tang/china_southern_power_grid_stat`，类别选择
   `Integration`。
3. 安装后重启 Home Assistant。

### 手动安装

从 [Releases](https://github.com/benj-tang/china_southern_power_grid_stat/releases)
下载发布包，将其中的 `china_southern_power_grid_stat` 目录复制到：

```text
<config>/custom_components/china_southern_power_grid_stat
```

重启 Home Assistant 后，在“设置 → 设备与服务 → 添加集成”中搜索
`China Southern Power Grid Statistics`。

## 登录与更新

- 支持短信验证码、短信验证码加密码、南网 App、微信和支付宝扫码登录。
- 默认每 4 小时更新，可在集成选项中调整。
- 上月和上年数据在稳定后降低刷新频率；需要立即重取时可重载集成。
- 5 分钟换码是本地防陈旧保护，不代表南网官方公布的二维码有效期。

## 隐私与安全

- 不要在 issue、日志或截图中提交手机号、缴费号、姓名、地址、二维码、Cookie、
  登录令牌或完整 API 响应。
- 登录令牌由 Home Assistant 私有配置存储管理；本集成不持久化交互式登录密码。
- 网络请求仅允许访问南网 `95598.csg.cn` 端点。
- 安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。

## 开发

```sh
uv sync --dev
uv run ruff check .
uv run pytest -q
```

贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 致谢与许可

本维护版基于 [CubicPill/china_southern_power_grid_stat](https://github.com/CubicPill/china_southern_power_grid_stat)，
并选择性吸收 `elvinsophus`、`seagaruda`、`L1yp` 等社区维护者的修复；具体提交与
作者归属记录在 Git 历史和 [MAINTENANCE.md](MAINTENANCE.md) 中。

项目按 [GNU GPL v3](LICENSE) 发布。
