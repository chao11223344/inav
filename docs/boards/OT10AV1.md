# OT10AV1 测试固件

本适配基于官方 INAV **8.0.1** 标签（基础提交
`ae47bcba018270eb5db6f04bef7dbde2b781d579`），新增独立目标
`OT10AV1`，USB 产品名 `OT10AV1`，板标识 `OT10`。这不是整仓升级到 INAV 10。
使用与 INAV 8 对应的 Configurator。

## 硬件与引脚

按板主确认：除下列差异和 IMU 外，其余接线、晶振和安装方向沿用
SpeedyBee F405 WING：STM32F405xG、8 MHz HSE。

| 功能 | OT10AV1 配置 |
| --- | --- |
| IMU | LSM6DSK320X，SPI1，PA5 SCK / PA6 MISO / PA7 MOSI / PA4 CS，CW270 |
| 看门狗 WDI | PA8，STWD100NYWY3F，禁用原灯带功能 |
| 电压 / 电流 | PC0 / PC1，比例沿用原板，实板需要校准 |
| 模拟 RSSI | PC4，ADC_CHN_3 |
| 模拟空速 AIR_OUT | PC5，ADC_CHN_4 |
| PWM1–PWM10 | PB7、PB6、PB0、PB1、PC8、PC9、PB14、PA15、PB10、PB11 |
| PON 控制 | PB15，PINIO2 → USER2，不再作为 PWM11 |
| 原 PINIO1 | PC13 → USER1 |

UART、I2C、SD 卡、OSD、蜂鸣器和 LED 沿用基础板。默认串口：UART1 CRSF、
UART3 GPS、UART6 MSP。PWM 实际分配由混控和输出协议决定；同一定时器的
输出仍受频率/协议共用约束。

## IMU 驱动来源

移植自官方 `maintenance-10.x` 提交
[`2527f7764f6394ee344a3edafb5a98f3b222e03a`](https://github.com/iNavFlight/inav/blob/2527f7764f6394ee344a3edafb5a98f3b222e03a/src/main/drivers/accgyro/accgyro_lsm6dxx.c)
中的 LSM6DXX 驱动和头文件，包含 `WHO_AM_I = 0x75` 识别、专用寄存器布局、
LSM6DSK320X 必需的 CTRL6 bit 3、陀螺仪 8 kHz / ±2000 dps、
加速度计 1 kHz / ±16 g，以及陀螺仪方向赋值。
旧型号 DSO/DSL 的高通滤波配置保留本地行为，未引入上游对此的独立修改。

## 看门狗行为

- GPIO 初始化后立即配置 PA8 为推挽输出，初始低电平；正常每 100 ms 翻转一次。
- 启动期间由 SysTick 喂狗，最多持续 30 秒，覆盖传感器初始化中的延时。
- 主循环开始执行后仅由主循环喂狗，SysTick 不再喂狗；因此主循环挂起时，
  外部看门狗仍可触发复位。USB 存储模式由其前台循环喂狗。
- 不使用自主持续输出的 PWM 喂狗，PA8 不占用电机/舵机定时器。
- 30 秒是软件启动宽限，**不是 STWD100 的硬件超时时间**。

本次 ST 数据手册下载受阻，未能从原文核对具体后缀的时序容差；
100 ms 翻转方案仍需用实板确认。测量 PA8 的边沿间隔，并验证停止前台运行
后外部看门狗确实拉动复位线。

固件只控制 WDI；没有提供 EN 引脚连接，无法在软件中禁止外部看门狗。
STM32 ROM DFU 不执行本固件，若外部看门狗在 DFU 期间仍使能并连接 NRST，
需由硬件/夹具禁止看门狗才能可靠刷写。F405 内部 Flash 擦除可能阻塞取指和
中断，首次配置初始化与 CLI `save` 也必须验证不会触发外部复位；
本实现没有在 RAM 中执行擦除期间的喂狗代码。

## PON 默认行为

GPIO 初始化后，USER2 未激活时 PB15 输出低电平，USER2 激活时输出高电平。
该默认值由软件选择，**未假定低电平等于 PON 关断**；通路实际极性取决于电路。
复位至 GPIO 初始化前的电平由硬件上下拉决定。

在 Configurator 的 Modes 中把 USER2 绑定到开关，分别测量 PB15 电平及 PON
通路导通/关断状态。默认 `pinio_box2 = 48`。如需反相，可在目标头文件中添加
`#define PINIO2_FLAGS PINIO_FLAGS_INVERTED` 后重新编译。

## 构建和主机验证

```sh
cmake -S . -B build
cmake --build build --target OT10AV1 -j4
python3 src/test/ot10av1_watchdog_test.py
```

已完成 OT10AV1 与 SPEEDYBEEF405WING 编译、看门狗真实 C 代码的主机测试
（启动、翻转间隔、启动超时、主循环停滞、计时回绕）。编译仅出现 LTO 串行
链接提示。OT10AV1 占用 FLASH 615100 B、普通 RAM 92296 B。
以上验证不代替实板测试。

## 上板验证

先拆桨，使用测试负载，首次刷写清除旧板配置，不直接恢复 SpeedyBee 的完整 dump。

1. 上电观察至少一分钟，确认无周期性复位；测试首次配置保存、后续 `save`
   与重启。测量 PA8 正常约 100 ms 一个边沿，并验证停喂后的复位。
2. `status` 确认 IMU 检出；转动板子核对模型的滚转、俯仰、偏航方向，完成加速度计校准。
3. 按混控配置逐一测 PWM1–PWM10，特别是 PB11；确认 PB15 不随输出测试变化。
4. USER2 开关测试 PB15 和 PON 的实际通断。
5. 分别向 RSSI/空速输入施加符合电路范围的测试信号，确认通道没有互换。

模拟输入测试可使用以下配置（会改变 RSSI 来源，测试结束按接收机需求恢复）：

```text
feature RSSI_ADC
set rssi_source = ADC
set rssi_adc_channel = 3
set pitot_hardware = ADC
set airspeed_adc_channel = 4
save
```

PC5 已接入 INAV 模拟空速通道，但现有 ADC 空速驱动按 MPXV7002DP 及 1:1
分压模型换算。OT10 空速放大器的传递函数尚未提供，不能据此认定显示空速
已经准确；先验证 ADC 通道，再根据实际传感器/放大电路校准或修改换算。

交付目录 `output_fw/OT10AV1/` 包含 HEX、BIN、SHA256 和本说明。
HEX 内含烧录地址；BIN 烧录起始地址为 `0x08000000`。
