# 一鸣 (Yiming) 真鲜奶吧 集成 for Home Assistant

将「一鸣真鲜奶吧」微信小程序的账户数据接入 Home Assistant。基于小程序抓包逆向，使用 `token` 鉴权头（明文，非 Bearer）。

## 功能特性

- 💰 储值余额 / 积分 / 会员等级 / 会员到期日 / 成长值
- 🎟️ 优惠券数量 / 可领优惠券（含明细）/ 可用优惠券
- 👤 会员姓名 / 用户基础信息 / 默认地址
- 🏪 最近门店 / App 公告
- 📊 最近订单 / 最近积分变动 / 最近交易 / 会员权益层级
- 📱 付款二维码（周期刷新）
- 🤖 自动领券 + 点单能力：共 15 个 service
- 🌐 中英文翻译（zh-Hans / en）
- 🎨 品牌图标与制造商 logo（自动在 HA 集成列表中显示）

## 安装

通过 HACS → 自定义仓库，添加本仓库（类别：集成）；或直接下载 `custom_components/yiming` 放入 HA 配置目录后重启。

## 配置

添加集成后，输入从小程序抓包得到的 `token` 即可。`token` 为明文请求头，长期有效（实测跨会话可用）。也支持手机号 + 短信验证码登录（自动获取 token）。

## 选项（集成设置）

进入集成 → 配置，可设置：

- **位置传感器（可选）**：选一个 HA 里的 GPS 传感器实体（如手机 App 的 `sensor.*_geocoded_location`），用于「最近门店」与门店搜索的定位。不选则回退到 HA 家庭地址。
- **默认门店**：输入门店名称关键字（如“一鸣”）后搜索，从结果下拉中选择；留空则自动使用最近门店。
- **默认地址**：无需设置。集成自动读取你一鸣账户里的默认收货地址（`默认地址` 传感器即展示它），下单时直接取用，无需手工填 ID。

## 传感器

共 17 个传感器，实体名称随 HA 界面语言自动切换中英文（依赖 `translation_key`）。下表给出 `translation_key` 与中英对照：

| translation_key | 中文名 | English |
|------|------|------|
| `balance` | 储值余额 | Stored Balance |
| `points` | 积分 | Points |
| `member_level` | 会员等级 | Membership Level |
| `member_expiry` | 会员到期 | Membership Expiry |
| `coupon_count` | 优惠券数量 | Coupon Count |
| `member_name` | 会员姓名 | Member Name |
| `growth_value` | 成长值 | Growth Value |
| `app_notice` | App 公告 | App Notice |
| `claimable_coupons` | 可领优惠券 | Claimable Coupons |
| `recent_orders` | 最近订单数 | Recent Orders |
| `usable_coupons` | 可用优惠券 | Usable Coupons |
| `integral_detail` | 最近积分变动 | Latest Points Change |
| `member_equity` | 会员权益层级 | Membership Equity Tiers |
| `transaction_details` | 最近交易 | Latest Transactions |
| `default_address` | 默认地址 | Default Address |
| `nearest_store` | 最近门店 | Nearest Store |
| `payment_qrcode` | 付款二维码 | Payment QR Code |

多账户时实体 ID 后缀递增（`_2`、`_3` …）。

## 服务

共 15 个 service，名称同样随语言切换。

### 领券
- `yiming.receive_all_coupons` — 遍历所有一鸣账户，领取全部「当前可领」优惠券（`residueCount > 0`）。
- `yiming.receive_coupon` — 领取指定券，参数：`equity_pool_id` / `coupon_code` / `receive_num`。

### 点单（供 AI / 自动化调用）
- `yiming.get_nearest_store` — 获取最近门店。
- `yiming.get_menu` — 获取门店菜单（`shop_code`）。
- `yiming.get_sku_info` — 获取商品 SKU 详情（`goods_id` / `shop_code`）。
- `yiming.search_stores` — 搜索门店（`keyword` / `city`）。
- `yiming.get_delivery_time` — 获取配送时段（`store_code` / `order_type`）。
- `yiming.get_default_address` — 获取默认地址。
- `yiming.get_nearby_addresses` — 获取附近地址。
- `yiming.calculate_cart` — 计算购物车（`goods_list`）。
- `yiming.pre_create_order` — 预创建订单（`shop_code` / `goods_list`）。
- `yiming.submit_order` — 提交订单（`shop_code` / `goods_list` / `order_type` / `pay_type` / `deliver_type` 等）。
- `yiming.get_order` — 查询订单（`order_no`）。

### 登录
- `yiming.send_sms_code` — 发送短信验证码（`mobile`）。
- `yiming.register_by_sms` — 短信验证码登录，返回 token（`mobile` / `verify_code`）。

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

当前版本：1.0

## 💝 赞助

如果这个集成帮到了你，欢迎请我喝杯咖啡 ☕

| 微信支付 | 支付宝 |
|:--------:|:------:|
| ![微信](sponsor/wechat.jpg) | ![支付宝](sponsor/alipay.jpg) |
