# 商業資料分析與挖掘互動設計 v1

## 現況對比與靠攏路線

## 範圍

本文件對比以下兩部分：

- 設計基線：同 packet 中的 `TASK-PACKET.md`
- 現況實作：`src/xenix/ui/`、`src/xenix/services/` 內與首頁、場景流程、訓練、推論、歷史、設定相關的實作

本文件回答的核心問題是：

- 目前軟體的互動模式和這份 SVG 設計有哪些對齊點
- 還需要補哪些能力，才能讓整體互動模式向 SVG 靠攏
- 現況中有哪些額外技術性表達，需要收斂成更接近設計語義的產品表達

## 來源定位狀態

原始 SVG 內容已完成轉寫，轉寫結果見 `TASK-PACKET.md`。

本次重新確認檔案位置時，原先的 `C:\Users\yyh\Downloads\商业数据分析与挖掘交互设计 v1.svg` 已經失效。這一輪在 `C:\Users\yyh` 與 `F:\CODING` 內未重新定位到同名檔案，因此本 packet 目前以既有轉寫內容作為對照基線。

## 本次盤點的主要實作檔案

- `src/xenix/ui/main_window.py`
- `src/xenix/ui/scenario_home_view.py`
- `src/xenix/ui/scenario_data_preparation_dialog.py`
- `src/xenix/ui/scenario_training_dialog.py`
- `src/xenix/ui/scenario_inference_dialog.py`
- `src/xenix/ui/inference_history_dialog.py`
- `src/xenix/ui/settings_dialog.py`
- `src/xenix/ui/widgets/file_drop_zone.py`
- `src/xenix/ui/widgets/dataset_summary.py`
- `src/xenix/ui/widgets/column_selection.py`
- `src/xenix/ui/widgets/inference_row_editor.py`
- `src/xenix/services/scenario_template_service.py`
- `src/xenix/services/scenario_workflow_service.py`
- `src/xenix/services/dataset_service.py`
- `src/xenix/services/inference_history_service.py`
- `src/xenix/services/ml_service.py`
- `src/xenix/services/storage/models.py`

## 現況互動模式摘要

### 首頁

目前首頁已經採用場景模式入口。主畫面只放：

- 場景卡片
- History
- Settings

首頁由 `ScenarioHomeView` 驅動，主視窗由 `MainWindow` 承接後續流程。

### 主流程骨架

目前軟體已經形成一條明確的 A -> B -> C 路徑：

1. `ScenarioDataPreparationDialog`
2. `ScenarioTrainingDialog`
3. `ScenarioInferenceDialog`

這條骨架和 SVG 的主流程方向一致。

### 場景資料準備

目前資料準備畫面已具備：

- 拖拽上傳
- 檔案選擇
- 資料摘要
- 自變量與因變量選擇
- 繼續到訓練

資料準備完成後，`ScenarioWorkflowService` 會建立隱藏的 scenario project、dataset 與 work item。

### 訓練

目前訓練畫面已具備：

- 固定訓練計畫自動啟動
- 步驟列表
- 任務狀態
- 最佳模型摘要
- `Run Full Plan Again`
- `Continue to Prediction`

### 推論

目前推論畫面已具備：

- 單筆輸入
- 批次檔案輸入
- 任務表
- 結果開啟
- 結果導出

推論階段以最佳模型為默認執行模型。

### 歷史與設定

目前歷史與設定都已經具備獨立對話框：

- 歷史頁以成功完成且帶有持久化結果的推論任務為來源
- 設定頁提供語言切換、執行路徑資訊與開啟日誌目錄

## 已對齊的部分

以下部分已經和 SVG 設計形成明顯對齊：

### 1. 首頁結構

首頁已經是場景導向入口，並且把 Settings 與 History 提升為一級入口。

### 2. 引導式三段流程

現況已經具備資料準備、訓練、推論三段式流程，這為靠攏 SVG 提供了很好的骨架。

### 3. 上傳與欄位映射

目前已支援檔案拖拽、檔案選擇、自變量與因變量映射，且後端已有輸入欄位、輸出欄位、欄位衝突等驗證規則。

### 4. 自動訓練與最佳模型

目前已支援固定訓練計畫、自動評估、最佳模型決策與後續推論承接。

### 5. 單筆推論與批次推論

目前推論畫面已經有單筆與批次兩種輸入方式，這一點和 SVG 的推論分流結構一致。

### 6. 歷史語義

目前 History 已經以推論結果為聚合單位，並支援時間排序與時間範圍篩選，這部分和 SVG 要求高度一致。

### 7. 設定分離

Settings 已經是獨立視窗，並承接語言與執行環境資訊，這和 SVG 的方向一致。

## 需要新增的部分

以下能力是向 SVG 靠攏時最直接的增量工作。

## A. 入口與場景模型

### 1. 新增「新任務 / 選擇過往模型」雙入口

SVG 的起點有兩條清楚路徑：

- 新任務
- 選擇過往模型

目前首頁直接從場景卡片進入資料準備。要靠攏 SVG，需要在首頁補出這個分流層，或在首頁卡片之上加入一個更高階的起始選擇。

### 2. 擴充場景目錄

目前 `ScenarioTemplateService` 只提供兩個業務模板：

- `sales_demand_forecast.v1`
- `customer_outcome_classification.v1`

SVG 表達的是更廣的分析場景集：

- 預測
- 分類
- 聚類
- 異常檢測
- 關鍵因素分析

因此需要新增一層場景註冊與展示機制，讓首頁或新任務入口能表達這組分析場景。

### 3. 補上「選擇過往模型」完整路徑

目前 scenario flow 以新訓練後的最佳模型為核心。SVG 需要另一條完整路徑：

1. 選擇場景
2. 查看過往模型列表
3. 按時間排序
4. 切換模型時顯示模型資訊
5. 確認後直接進入預測

這條路徑需要新的 UI、查詢接口與模型資訊組裝。

## B. 資料準備頁

### 1. 新增前 5 筆資料預覽

SVG 要求在資料載入後顯示前 5 筆。

目前 `DatasetInspection` 只返回：

- file name
- path
- format
- row count
- column count
- column metadata

要靠攏 SVG，需要在 `dataset_inspection.py` 與 `DatasetSummaryWidget` 周邊加入資料預覽能力。

### 2. 將按鈕啟用條件前移到 UI

SVG 對按鈕啟用條件定義得很明確：

- 有效的輸入項與輸出項配置後，才可以開始訓練
- 單筆資料完整後，才可以開始預測
- 批次檔案載入成功後，才可以開始預測

目前多數條件由後端在提交時驗證，前端按鈕仍可先點擊。要靠攏 SVG，需要把這些條件同步到 UI 狀態層。

### 3. 強化上傳狀態與頁面引導

SVG 的資料頁強調：

- 檔案載入前後的隱藏 / 顯示狀態
- 明確的拖拽提示
- 明確的按鈕語義

目前畫面已經具備基礎結構，接下來需要加入更完整的狀態回饋與可見性控制。

### 4. 補上返回上一步語義

SVG 為新任務路徑定義了一個返回動作，並且要求返回後清空舊的暫存選擇。現況 A -> B -> C 流程中，這個行為還沒有明確的 UI 承載點。

## C. 模型選擇與訓練頁

### 1. 新增「選擇模式」

SVG 的核心差異點在於訓練前有一個可展開的模型選擇模式：

- 模型區平時隱藏
- 展開後可以勾選模型
- 可配置參數
- 可保存為默認值

目前 `ScenarioTrainingDialog` 直接啟動固定訓練計畫。要靠攏 SVG，需要在資料頁和訓練頁之間插入一個模型選擇層，或把這一層整合進訓練前狀態。

### 2. 新增模型勾選、參數編輯、默認值保存

SVG 要求：

- 模型多選
- 每個模型有參數區
- 部分模型默認勾選
- 當前勾選組合可保存為默認值

現況後端已有模型、參數、param grid 的技術基礎，前端 scenario flow 尚未暴露這種可配置模型組合。

### 3. 新增模型刪除

SVG 的模型選擇頁與過往模型頁都包含刪除模型的動作。現況資料庫與服務層還沒有對應的模型刪除流程。

### 4. 新增模型資訊展示

SVG 對每個模型希望展示：

- 模型名稱
- 訓練狀態
- `MSE`
- `R平方`
- 相關提示文案

目前訓練頁有步驟表和最佳模型摘要。要靠攏 SVG，需要把結果視圖從任務步驟視角轉成模型結果視角，並且在 UI 中明確露出指標含義。

### 5. 新增模型保存操作與保存後鎖定

SVG 區分了：

- 整體性的「保存模型」
- 候選模型級別的「保存該模型」
- 保存後按鈕不可再次點擊

現況後端會在任務成功時持久化模型檔，但 UI 還沒有顯式的保存互動與保存狀態管理。

### 6. 新增模型保存說明與命名規則

SVG 為模型保存定義了很具體的產品語義：

- 檔名規則
- 備註內容
- 變量清單
- 樣本資料
- 評估值

現況 `TrainedModelRow` 只保存：

- work_item_id
- ml_task_id
- model_key
- problem_kind
- artifact_path

要靠攏 SVG，需要新增一層面向使用者的模型 metadata 結構。

## D. 推論頁

### 1. 補上推論選擇頁

SVG 把「單個資料預測」與「文件輸入預測」表達為一個選擇頁。現況用 tab 直接承載這兩種模式。這一點屬於中等差距，調整方向可以是：

- 保持 tab，補足 SVG 所需的狀態與文案
- 改成顯式選擇頁，再進入具體操作頁

### 2. 新增批次檔案前 5 筆預覽

SVG 對批量預測資料要求顯示前 5 筆預覽。現況批次頁只列出檔案路徑清單。

### 3. 新增結果直接預覽

SVG 期待：

- 單筆結果直接顯示
- 批量結果直接顯示前 5 筆
- 結果裡展示因變量名稱

現況推論頁偏向「任務列表 + 任務詳情 + 打開結果檔」模式。這裡需要補一層面向使用者的結果視圖。

### 4. 新增按模型發起預測

SVG 為每個候選模型都放置「選擇該模型預測」按鈕。現況 scenario flow 固定使用最佳模型。要靠攏 SVG，需要在推論階段支援：

- 指定某個已訓練模型進行預測
- 每次切換模型即刷新預測結果

### 5. 完整落地按鈕啟用規則

目前推論頁仍以任務提交時的驗證為主。SVG 需要更細的互動約束：

- 單筆輸入完整後啟用預測
- 批次檔案載入成功後啟用預測

這部分需要把資料完整性檢查前移到 UI。

## E. 過往模型管理

SVG 對過往模型路徑定義得很明確，現況對應能力還需要建立：

- 模型列表查詢
- 最新優先排序
- 模型資訊卡或資訊面板
- 場景與模型的關聯
- 模型刪除
- 模型確認後直接進入預測

這一塊建議作為一個獨立工作包來做，因為它會同時影響首頁、模型儲存結構、推論入口與模型 metadata。

## 需要收斂的部分

以下部分屬於「現況已有能力，表達方式偏技術化」，往 SVG 靠攏時需要重寫成更接近業務語義的產品表達。

### 1. 訓練頁的任務表、任務詳情與原始日誌

SVG 的訓練頁重心是：

- 模型結果
- 指標
- 可以直接走向預測

目前 `ScenarioTrainingDialog` 將：

- 計畫步驟表
- 任務詳情
- 原始日誌

都放在主視圖。這些能力很適合保留成 Advanced 區，而主視圖可以改成更直觀的模型卡片或結果摘要。

### 2. 推論頁的任務視角

SVG 的推論頁重心是輸入資料與結果。現況推論頁以任務表、任務詳情、檔案路徑為主要結果承載。靠攏方向是：

- 主視圖展示輸入與結果
- 任務表與日誌下沉為進階資訊

### 3. 資料摘要的技術資訊佔比

目前 `DatasetSummaryWidget` 以：

- path
- format
- row count
- column count

為核心。SVG 更重視檔案預覽與任務可開始性，因此這一區可以重排成更偏操作導向的摘要。

### 4. 最佳模型單一路徑

目前 scenario flow 緊密綁定「最佳模型」這個概念。SVG 允許使用者在多個候選模型之間切換與保存，產品表達上會更接近「模型選擇與模型運營」而非單一自動最佳模型流程。

## 現況中額外存在的能力

現況有一些能力已經超出 SVG 的字面要求。這些能力可以保留，並且放進進階層：

- 技術工作台 `DatasetWorkspace`、`MLWorkspace`、`InferenceWorkspace`
- 訓練與推論任務詳細日誌
- 推論歷史中的 scenario 名稱展示
- 設定頁中的完整執行目錄資訊

這些能力很適合做成：

- 開發者模式
- 進階模式
- 展開區

## 靠攏 SVG 的建議工作拆分

以下拆分兼顧現有骨架可重用性與 SVG 靠攏程度。

### 工作包 1：入口重構

目標：

- 建立「新任務 / 選擇過往模型」雙入口
- 建立新的場景目錄

主要工作：

- 重構 `ScenarioHomeView`
- 新增場景 registry
- 新增過往模型入口承接頁

實作狀態：

- 已完成第一輪落地，日期為 `2026-04-23`

本輪已完成：

- 首頁改為雙入口模式，先選 `新任務` 或 `選擇過往模型`，再選分析場景
- 新增分析場景 registry，首頁場景層改為：
  - `預測`
  - `分類`
  - `聚類`
  - `異常檢測`
  - `關鍵因素分析`
- `預測` 與 `分類` 已接到現有模板流程
- `聚類`、`異常檢測`、`關鍵因素分析` 先以 `planned` 狀態保留在入口層
- `新任務 -> 預測` 會承接到既有 `ScenarioDataPreparationDialog`
- `選擇過往模型 -> 預測` 會進入新的 `PreviousModelFlowDialog` 骨架頁
- 首頁與過往模型骨架頁已補上中英文翻譯資產
- 既有 UI / i18n 測試已更新為新的雙入口互動模型

涉及檔案：

- `src/xenix/services/analysis_scenario_service.py`
- `src/xenix/ui/analysis_scenario_text.py`
- `src/xenix/ui/previous_model_flow_dialog.py`
- `src/xenix/ui/scenario_home_view.py`
- `src/xenix/ui/main_window.py`
- `src/xenix/app.py`
- `src/xenix/translations/xenix_en_US.ts`
- `src/xenix/translations/xenix_en_US.qm`
- `src/xenix/translations/xenix_zh_CN.ts`
- `src/xenix/translations/xenix_zh_CN.qm`
- `tests/test_scenario_ui.py`
- `tests/test_i18n.py`

驗證結果：

- `python -m compileall src tests scripts` 已通過
- 以手寫 UI harness 驗證以下行為已通過：
  - 英文首頁雙入口顯示正確
  - `新任務 -> 預測` 可打開資料準備頁
  - `選擇過往模型 -> 預測` 可打開過往模型骨架頁
  - 切換 `zh_CN` 後，首頁與過往模型骨架頁文案會正確切換為中文
- `pytest tests/test_scenario_ui.py tests/test_i18n.py` 在目前沙箱環境下被 `pytest` 自建暫存目錄 ACL 擋住，屬於環境限制，這一輪沒有形成產品邏輯失敗

對工作包 2 的直接影響：

- 首頁入口語義已穩定，下一包可以直接從 `新任務` 分支往下強化資料準備頁
- `選擇過往模型` 路徑目前保持骨架狀態，後續可在工作包 6 接上模型列表、排序與確認流程

### 工作包 2：資料準備頁強化

目標：

- 補上資料前 5 筆預覽
- 把欄位有效性、按鈕啟用條件與可見性規則前移到 UI

主要工作：

- 擴充 `DatasetInspection`
- 重寫 `DatasetSummaryWidget`
- 在 `ScenarioDataPreparationDialog` 補足狀態與返回語義

### 工作包 3：模型選擇模式

目標：

- 在訓練前提供模型選擇、參數調整與默認組合保存

主要工作：

- 新增模型選擇頁或訓練前配置區
- 建立默認模型組合持久化
- 加入模型刪除操作

### 工作包 4：訓練結果視圖重寫

目標：

- 將訓練頁主視圖轉成模型結果視圖

主要工作：

- 以模型卡片替代表格中心視角
- 顯示 `MSE`、`R平方` 與提示說明
- 補上保存模型與保存狀態

### 工作包 5：推論頁靠攏

目標：

- 讓推論頁更接近「輸入 -> 結果」而不是「任務 -> 檔案」

主要工作：

- 補上單筆與批量的結果預覽
- 補上批次檔案前 5 筆預覽
- 支援按指定模型預測
- 補上精確的按鈕啟用條件

### 工作包 6：過往模型路徑

目標：

- 完成 SVG 中的模型回用路徑

主要工作：

- 模型查詢、排序、資訊展示
- 模型確認與刪除
- 直接承接到推論

### 工作包 7：模型 metadata 與保存語義

目標：

- 讓模型保存具備 SVG 所要求的產品語義

主要工作：

- 增加模型保存說明結構
- 增加命名規則
- 增加訓練來源、欄位、樣例、評估值的持久化

## 我們真正要做的事

如果目標是讓軟體的用戶互動模式向這份 SVG 靠攏，核心工作可以濃縮成一句話：

把目前「固定模板自動訓練 + 最佳模型自動推論」的流程，擴展成「場景分流 + 模型可見 + 模型可選 + 結果直讀」的流程。

最關鍵的改動集中在四個產品層：

- 入口層：雙入口與場景目錄
- 訓練前層：模型選擇模式
- 推論層：按模型預測與結果直讀
- 模型資產層：過往模型回用與 metadata

## 優先順序建議

若以最小可行靠攏路線來排，建議順序如下：

1. 入口重構
2. 資料準備頁強化
3. 模型選擇模式
4. 推論頁靠攏
5. 過往模型路徑
6. 模型 metadata 完整化

這個順序可以最大化重用現有的 A -> B -> C 骨架，也能最快把整體互動模式拉近到 SVG 的語義。
