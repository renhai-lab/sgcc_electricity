<h1 align="center">国家电网电力获取</h1>
<p align="center">
<img src="assets/image-20230730135540291.png" alt="mini-graph-card" width="400">
</p>




本应用可以帮助你将国网的电费、用电量数据接入HA，或者保存到本地。具体提供两类数据：

1. 在homeassistant以实体显示：

   ```
   sensor.last_electricity_usage：最近一天用电量
   sensor.electricity_charge_balance：预付费显示电费余额，反之显示上月应交电费
   sensor.yearly_electricity_usage： 今年总用电量
   sensor.yearly_electricity_charge:  今年总用电费用
   ```

1. 近三十天每日用电量数据。

## 一、适用范围：

适用于除南方电网覆盖省份外的用户。即除广东、广西、云南、贵州、海南等省份的用户外，均可使用本应用获取电力、电费数据。

不管是通过哪种哪种安装的homeassistant，只要可以运行python，都可以采用本仓库部署。

## 二、实现流程

通过python实现selenium获取国家电网的数据，通过homeassistant的提供的[REST API](https://developers.home-assistant.io/docs/api/rest/)将采用POST请求将实体状态更新到homeassistant。

## 三、安装

### 方法一：docker镜像部署，速度快 
1. 安装docker，方法自行百度

2. 创建项目文件夹

   ```bash
   mkdir sgcc_electricity & cd sgcc_electricity 
   ```

3. 创建环境变量文件

   ```bash
   vim .env
   ```

   参考以下文件编写.env文件

   ```bash
   # 国网登录信息
   PHONE_NUMBER="xxx" # 手机号
   PASSWORD="xxxx" # 密码
   
   # 数据库配置
   MONGO_URL="mongodb://USERNAME:PASSWORD@localhost:27017/"
   DB_NAME="homeassistant"
   # COLLECTION_NAME默认为electricity_daily_usage_{国网用户id}
   
   # homeassistant配置
   HASS_URL="http://localhost:8123/" # homeassistant地址
   HASS_TOKEN="token" # 长期令牌
   
   # selenium运行参数
   JOB_START_TIME="07:00"
   
   # 以下文件不一定需要修改 单位都为秒
   DRIVER_IMPLICITY_WAIT_TIME=60
   RETRY_TIMES_LIMIT=5
   LOGIN_EXPECTED_TIME=60
   RETRY_WAIT_TIME_OFFSET_UNIT=10
   FIRST_SLEEP_TIME=10
   
   # 日志级别
   LOG_LEVEL="INFO" # DEBUG 可以查看报错信息
   ```

4. 编写docekr-compose.yml文件

   ```bash
   vim docekr-compose.yml
   ```

   填入以下内容

   ```yaml
   version: "3"
   
   services:
     app:
       env_file:
         - .env
       image: renhai/sgcc_electricity:latest
       container_name: sgcc_electricity
       network_mode: bridge
       environment:
         - SET_CONTAINER_TIMEZONE=true
         - CONTAINER_TIMEZONE=Asia/Shanghai
       restart: unless-stopped
       command: python3 main.py
   
   # 默认将近30天数据写入mongo数据库，方便查询
     mongo:
       image: mongo:4.4.18
       restart: always
       container_name: mongo-for-sgcc
       network_mode: bridge
       environment:
         MONGO_INITDB_ROOT_USERNAME: USERNAME # 修改为自己的用户名
         MONGO_INITDB_ROOT_PASSWORD: PASSWORD # 修改为自己的密码
         MONGODB_DATABASE: "homeassistant" # 修改为自己的数据库名,和.env中的数据库名一致
         CONTAINER_TIMEZONE: Asia/Shanghai
       volumes:
         - ./db:/data/db
       ports:
         - "27017:27017"
   ```

### 方法二：本地自行构建容器

1. 克隆仓库

   ```bash
   git clone https://github.com/renhaiidea/sgcc_electricity.git \
   & cd sgcc_electricity
   ```

2. 参考sample.env编写.env文件

   ```
   cp sample.env ./env
   ```

3. 查阅docker-compose文件，默认不需要修改

4. 运行

   ```bash
   docker compose up --build 
   # 或者后台运行
   docker compose up -d --build
   ```

### 方法三，不推荐，不安装docker，安装python环境后直接运行：

克隆仓库之后,参考Dockerfile的命令，<u>自行配置安装chrome浏览器和浏览器驱动</u>，安装mongodb，将sample.env文件复制scripts文件夹，到然后运行mian.py文件。



## 四、配置与使用

### 1.**！！！ 第一次运行需要创建并填写.env文件，按文件说明进行填写。**

### 2.（可选）填写homeassistant的配置文件

由于采用REST API方式创建sensor，没有做实体注册，无法在webui里编辑。如果需要，你可以在configuration.yaml下增加如下配置后重启HA，这样你就可在webUI编辑对应的实体了，这样含有_entity后缀的实体就可以进行修改了。

- 如果你有一个户号，参照以下配置：

```yaml
# Example configuration.yaml entry
# 文件中只能有一个template
template:
  # 参考文档： https://www.home-assistant.io/integrations/template
	# trigger为原始sensor，实际请使用sensor中的实体。
  - trigger:
      - platform: event
        event_type: "state_changed"
        event_data:
          entity_id: sensor.electricity_charge_balance
    sensor:
      - name: electricity_charge_balance_entity
        unique_id: electricity_charge_balance_entity
        state: "{{ states('sensor.electricity_charge_balance') }}"
        state_class: measurement
        unit_of_measurement: "CNY"
        device_class: monetary
####################
  - trigger:
      - platform: event
        event_type: "state_changed"
        event_data:
          entity_id: sensor.last_electricity_usage
    sensor:
      - name: 最近一天用电量
        unique_id: last_electricity_usage_entity
        state: "{{ states('sensor.last_electricity_usage') }}"
        attributes:
          present_date: "{{ state_attr('sensor.last_electricity_usage', 'present_date') }}"
          last_updated: "{{ state_attr('sensor.last_electricity_usage', 'last_updated') }}"
        state_class: total
        unit_of_measurement: "kWh"
        device_class: energy
######################
  - trigger:
      - platform: event
        event_type: "state_changed"
        event_data:
          entity_id: sensor.yearly_electricity_usage
    sensor:
      - name: yearly_electricity_usage_entity
        unique_id: yearly_electricity_usage_entity
        state: "{{ states('sensor.yearly_electricity_usage') }}"
        state_class: total_increasing
        unit_of_measurement: "kWh"
        device_class: energy
######################
  - trigger:
      - platform: event
        event_type: "state_changed"
        event_data:
          entity_id: sensor.yearly_electricity_charge
    sensor:
      - name: yearly_electricity_charge_entity
        unique_id: yearly_electricity_charge_entity
        state: "{{ states('sensor.yearly_electricity_charge') }}"
        state_class: total_increasing
        unit_of_measurement: "CNY"
        device_class: monetary
############################################
```

- 如果你有多个户号，每个户号参照[configuration.yaml](template/configuration.yaml)配置。

  > **注：如果你有一个户号，在HA里就是以上实体名；如果你有多个户号，实体名称还要加 “_户号”后缀，举例:sensor.last_electricity_usage_1234567890**

### 3.（可选）ha内数据展示 [mini-graph-card](https://github.com/kalkih/mini-graph-card) 实现效果

![image-20230730135540291](assets/image-20230730135540291.png)

```yaml
type: custom:mini-graph-card
entities:
  - entity: sensor.last_electricity_usage_entity
    name: 国网每日用电量
    aggregate_func: first
    show_state: true
    show_points: true
group_by: date
hour24: true
hours_to_show: 240
```

### 4.（可选）配合用电阶梯，实现实时电价。

![image-20230729172257731](assets/image-20230729172257731.png)

#### 具体操作：

修改homeassistant.yml文件然后重启或重载配置文件，注意当前阶梯中的sensor.yearly_electricity_usage_entity要根据你的实际清空修改。：

```yaml
# 文件中只能有一个sensor
sensor:
  # 实时电价
  - platform: template #平台名称
    sensors: #传感器列表
      real_time_electricity_price: #实体名称：只能用小写，下划线
        unique_id: "real_time_electricity_price" #UID（必须）
        friendly_name:  '实时电价' #在前端显示的传感器昵称（可选)
        unit_of_measurement: "CNY/kWh" #传感器数值的单位（可选）
        icon_template: mdi:currency-jpy #默认图标
        value_template: > #定义一个获取传感器状态的模板（必须）下面的6和22是指6点和22点，"1""2""3"是指阶梯123，6个价格分别是3个阶梯的峰谷价格
          {% if now().strftime("%H")| int >= 6 and now().strftime("%H")|int < 22 and states("sensor.current_ladder")=="1" %}
            0.617
          {%elif now().strftime("%H")| int >= 6 and now().strftime("%H")|int < 22 and states("sensor.current_ladder")=="2" %}
            0.677
          {%elif now().strftime("%H")| int >= 6 and now().strftime("%H")|int < 22 and states("sensor.current_ladder")=="3" %}
            0.977
          {% elif states("sensor.current_ladder")=="1" %}
            0.307
          {% elif states("sensor.current_ladder")=="2" %}
            0.337
          {% elif states("sensor.current_ladder")=="3" %}
            0.487
          {% endif %}

# 当前阶梯
  - platform: template
    sensors:
      current_ladder:
        unique_id: "current_ladder"
        friendly_name:  '当前阶梯'
        unit_of_measurement: "级"
        icon_template: mdi:elevation-rise
        value_template: > #这里是上海的三个阶梯数值，第2阶梯3120，第三阶梯4800，为了统计准确，大家可以减去现如今已经用过的总度数
          {% if states("sensor.yearly_electricity_usage_entity") | float <= 3120 %}
          1
          {% elif states("sensor.yearly_electricity_usage_entity") | float >3120 and states("sensor.yearly_electricity_usage_entity") | float <= 4800 %}
          2
          {% else %}
          3
          {% endif %}
```

## 写在最后
> ~~原作者：[https://github.com/louisslee/sgcc_electricity](https://github.com/louisslee/sgcc_electricity)~~，原始[README_origin.md](归档/README_origin.md)。
>
> **有人同步过：**[https://github.com/liantianji/sgcc_electricity](https://github.com/liantianji/sgcc_electricity)

## 我的自定义部分包括：

增加的部分：

- 增加近30天每日电量写入数据库（默认mongodb）
- 将间歇执行设置为定时执行: JOB_START_TIME，默认为"07:00”
- 给last_daily_usage增加present_date，用来确定更新的是哪一天的电量。一般查询的日期会晚两天。
- configuration.yaml文件修改。
