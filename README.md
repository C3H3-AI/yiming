# 一鸣 (Yiming) 真鲜奶吧 集成 for Home Assistant

将「一鸣真鲜奶吧」微信小程序的账户数据接入 Home Assistant。基于小程序抓包逆向，使用 `token` 鉴权头（明文，非 Bearer）。

## 功能特性

- 💰 储值余额 / 积分 / 会员等级 / 会员到期日 / 成长值
- 🎟️ 优惠券数量 / 可领优惠券数量（含明细）
- 👤 会员姓名 / 用户基础信息
- 📢 App 公告
- 🤖 自动领券：提供 `receive_all_coupons` / `receive_coupon` 两个 service
- 🎨 品牌图标与制造商 logo（自动在 HA 集成列表中显示）

## 安装

通过 HACS → 自定义仓库，添加本仓库（类别：集成）；或直接下载 `custom_components/yiming` 放入 HA 配置目录后重启。

## 配置

添加集成后，输入从小程序抓包得到的 `token` 即可。`token` 为明文请求头，长期有效（实测跨会话可用）。

## 传感器

| 实体 | 说明 |
|------|------|
| `sensor.yi_ming_zhang_hu_chu_zhi_yu_e` | 储值余额 |
| `sensor.yi_ming_zhang_hu_ji_fen` | 积分 |
| `sensor.yi_ming_hui_yuan_deng_ji` | 会员等级 |
| `sensor.yi_ming_hui_yuan_dao_qi` | 会员到期日 |
| `sensor.yi_ming_cheng_zhang_zhi` | 成长值 |
| `sensor.yi_ming_you_hui_quan_shu` | 优惠券数 |
| `sensor.yi_ming_zhang_hu_ke_ling_you_hui_quan` | 可领优惠券数（含明细） |
| `sensor.yi_ming_hui_yuan_xing_ming` | 会员姓名 |
| `sensor.yi_ming_app_gong_gao` | App 公告 |

多账户时实体 ID 后缀递增（`_2`、`_3` …）。

## 服务

### `yiming.receive_all_coupons`
遍历所有一鸣账户，领取全部「当前可领」优惠券（`residueCount > 0`）。

### `yiming.receive_coupon`
领取指定券，参数：`equity_pool_id` / `coupon_code` / `receive_num`。

## 自动化示例

当「可领优惠券」数量变化时自动领取：

```yaml
automation:
  - alias: 一鸣自动领券
    trigger:
      - platform: state
        entity_id:
          - sensor.yi_ming_zhang_hu_ke_ling_you_hui_quan
          - sensor.yi_ming_zhang_hu_ke_ling_you_hui_quan_2
    action:
      - service: yiming.receive_all_coupons
```

## 版本

当前版本：0.1.0

## 💝 赞助

如果这个集成帮到了你，欢迎请我喝杯咖啡 ☕

| 微信支付 | 支付宝 |
|:--------:|:------:|
| ![微信](sponsor/wechat.jpg) | ![支付宝](sponsor/alipay.jpg) |

