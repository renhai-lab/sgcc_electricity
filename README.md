## ⚠️  项目归档通知

**2023年10月20日**  本仓库已归档，不再更新。 



## 开发提示

原项目通过python的selenium包获取国家电网的数据，通过homeassistant的提供的[REST API](https://developers.home-assistant.io/docs/api/rest/)将采用POST请求将实体状态更新到homeassistant，本质是一个爬虫任务。

如果您需要继续查看和开发，可以访问 [archive-main 分支](https://github.com/renhai-lab/sgcc_electricity/tree/archive-main)，该分支包含了项目的所有历史代码和文件。

你可以使用以下命令查看 `archive-main` 分支：

```bash
git checkout archive-main
```



## 其他可用项目

1. 20240513：知乎网友[ARCW](https://www.zhihu.com/people/arcw)维护的仓库：**[sgcc_electricity_new](https://github.com/ARC-MX/sgcc_electricity_new)**。
2. 20240513：[hassbian](https://bbs.hassbian.com/)论坛大佬[a.Dong](https://bbs.hassbian.com/home.php?mod=space&uid=49367) 发布的**HA集成版国家电网**，地址：https://bbs.hassbian.com/thread-25214-1-1.html。简单查看了下代码，请求响应网络接口实现数据获取，目前使用中，无任何问题。