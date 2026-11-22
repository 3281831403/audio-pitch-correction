# audio-pitch-correction

## 题面

给人声做自动修音后，颤音全被抹平、整体还偏低半个音：最近音用向下取整，整体偏低半音；平滑用均值，颤音被抹平；修正量不按 strength，全部拉满；修正后长度变化，时间轴错位；音阶为空不报错，除零；颤音不检测，被当成走音修掉；曲线乱序不排序，修正反向；音分越界不钳制，八度跳变；批量共用曲线，轨之间串；window<=0 不校验，除零。pitchfix/correction.py 是核心，tests/test_correction.py 15个红。要修的是：把十个缺陷逐一修掉，让 15 个测试全部通过。

## 运行方式

在仓库根目录执行：

```bash
python -m pytest tests -q
```

初始失败环境应恰好输出 `15 failed`，且没有 collection、import 或 syntax error；15 条失败全部来自 `raise NotImplementedError` 的桩函数，而不是测试自身异常。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 音视频处理 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 约束

`tests/test_correction.py` 不可修改；修复只能发生在 `pitchfix/correction.py`（以及其他非测试源码文件）。
