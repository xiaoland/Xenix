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

### 1. 首頁維持單層場景入口

首頁的產品語義整理如下：

- 選擇場景
- History
- Settings

點擊任一場景後，進入同一套流程。場景負責提供不同模板、不同默認模型組合與不同結果表達方式。

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

因此需要新增一層場景註冊與展示機制，讓首頁能表達這組分析場景。

### 3. 在資料準備後補上模型來源選擇層

依目前互動定義，資料準備完成後進入同一個第二步，讓使用者選擇模型來源：

- 選擇模型並訓練
- 選擇已訓練模型

這一層會消化「新模型訓練」與「已訓練模型回用」兩種語義，也讓系統可以基於場景、欄位映射與資料相容性來決定可供回用的模型集合。

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

SVG 為資料準備頁與後續步驟定義了返回動作，並且要求返回後清空舊的暫存選擇。現況 A -> B -> C 流程中，這個行為還沒有明確的 UI 承載點。

## C. 模型選擇與訓練頁

### 1. 新增「模型來源選擇」

SVG 的第二步聚焦模型來源選擇：

- 選擇模型並訓練
- 選擇已訓練模型

目前 `ScenarioTrainingDialog` 直接啟動固定訓練計畫。要靠攏 SVG，需要在資料頁和訓練頁之間插入一個模型來源選擇層。

### 2. 在訓練分支新增模型勾選、參數編輯、默認值保存

當使用者選擇 `選擇模型並訓練` 這條分支時，SVG 要求：

- 模型多選
- 每個模型有參數區
- 部分模型默認勾選
- 當前勾選組合可保存為默認值

現況後端已有模型、參數、param grid 的技術基礎，前端 scenario flow 尚未暴露這種可配置模型組合。

### 3. 新增模型刪除

SVG 的訓練分支與已訓練模型分支都包含刪除模型的動作。現況資料庫與服務層還沒有對應的模型刪除流程。

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

SVG 對已訓練模型回用路徑定義得很明確。這條路徑位於資料準備之後，現況對應能力還需要建立：

- 基於場景與欄位映射的模型相容性篩選
- 模型列表查詢
- 最新優先排序
- 模型資訊卡或資訊面板
- 場景與模型的關聯
- 模型刪除
- 模型確認後直接進入預測

這一塊建議作為一個獨立工作包來做，因為它會同時影響資料準備後的第二步、模型儲存結構、推論入口與模型 metadata。

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

### 工作包 1：首頁場景入口與場景目錄

目標：

- 首頁保留 `選擇場景`、`History`、`Settings`
- 建立新的場景目錄

主要工作：

- 重構 `ScenarioHomeView`
- 新增場景 registry
- 讓任一場景都承接同一套流程入口

實作狀態：

- 已完成第一輪落地，日期為 `2026-04-23`
- 同日已收斂產品定義：首頁採用單層場景入口，模型來源選擇位於第二步

本輪已完成：

- 新增分析場景 registry，首頁場景層改為：
  - `預測`
  - `分類`
  - `聚類`
  - `異常檢測`
  - `關鍵因素分析`
- `預測` 與 `分類` 已接到現有模板流程
- 首頁點擊可用場景後，會直接承接到既有資料準備頁
- `聚類`、`異常檢測`、`關鍵因素分析` 先以 `planned` 狀態保留在入口層
- 首頁與場景層已補上中英文翻譯資產
- 既有 UI / i18n 測試已更新為新的場景層互動模型

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
  - 英文首頁場景層顯示正確
  - `預測` 場景可打開資料準備頁
  - 切換 `zh_CN` 後，首頁場景層文案會正確切換為中文
- 與工作包 1 直接相關的 `pytest` 目標用例已通過

對工作包 2 的直接影響：

- `AnalysisScenarioService`、場景文案與場景卡片層可直接保留
- 現有來源分流元件與 `PreviousModelFlowDialog` 會在下一輪移入第二步

### 工作包 2：資料準備與模型來源分流

目標：

- 補上資料前 5 筆預覽
- 把欄位有效性、按鈕啟用條件與可見性規則前移到 UI
- 在資料準備後提供模型來源選擇：
  - `選擇模型並訓練`
  - `選擇已訓練模型`

主要工作：

- 擴充 `DatasetInspection`
- 重寫 `DatasetSummaryWidget`
- 在 `ScenarioDataPreparationDialog` 補足狀態與返回語義
- 新增資料準備後的模型來源選擇頁
- 建立已訓練模型分支的相容性查詢契約

實作狀態：

- 已完成第一輪落地，日期為 `2026-04-23`

本輪已完成：

- `DatasetInspection` 已補上前 5 筆預覽資料
- `DatasetSummaryWidget` 已補上資料預覽表格
- `ScenarioDataPreparationDialog` 已把欄位有效性前移到 UI
- 只有在輸入列與預測目標配置有效後，才可繼續到下一步
- 資料準備完成後，主流程已不再直接跳到訓練頁
- 新增 `ScenarioModelSourceDialog` 作為第二步
- 第二步已提供：
  - `選擇模型並訓練`
  - `選擇已訓練模型`
- 已新增 `ScenarioModelSourceService`，目前以場景隱藏專案中的既有工作項為來源，按：
  - 模板問題型別
  - 輸入列完整匹配
  - 預測目標完整匹配
  來查詢相容的已訓練模型
- 已訓練模型分支目前會承接到占位頁，完整直接復用到推論仍留在工作包 6

涉及檔案：

- `src/xenix/services/dataset_inspection.py`
- `src/xenix/services/scenario_model_source_service.py`
- `src/xenix/ui/scenario_data_preparation_dialog.py`
- `src/xenix/ui/scenario_model_source_dialog.py`
- `src/xenix/ui/previous_model_flow_dialog.py`
- `src/xenix/ui/main_window.py`
- `src/xenix/ui/widgets/column_selection.py`
- `src/xenix/ui/widgets/dataset_summary.py`
- `src/xenix/app.py`
- `src/xenix/translations/xenix_en_US.ts`
- `src/xenix/translations/xenix_zh_CN.ts`
- `tests/test_scenario_ui.py`

驗證結果：

- `python -m compileall src tests scripts` 已通過
- 與工作包 2 直接相關的目標用例已通過，包括：
  - 資料預覽與欄位有效性
  - 相容已訓練模型查詢
  - 主視窗從資料準備頁承接到第二步
  - `zh_CN` 下的既有首頁與主流程切換

### 工作包 3：新模型選擇與訓練模式

目標：

- 在 `選擇模型並訓練` 分支中提供模型選擇、參數調整與默認組合保存

主要工作：

- 新增模型選擇頁或訓練前配置區
- 建立默認模型組合持久化
- 加入模型刪除操作

實作狀態：

- 已完成第一輪落地，日期為 `2026-04-24`

本輪已完成：

- 新增 `ScenarioTrainingSelectionDialog`，作為 `選擇模型並訓練` 分支的訓練前配置頁
- 第二步的 `TRAIN_NEW` 分支已改為：
  - 先進入模型選擇與訓練模式
  - 再承接既有 `ScenarioTrainingDialog`
- 已支援按場景模板載入可用模型清單，並依模板既有訓練計畫排序
- 已支援模型多選
- 已支援每個模型在以下兩種訓練模式中擇一：
  - `Fit`
  - `Hyperparameter Tuning`
- 已支援依模型能力切換參數表單：
  - `param_schema`
  - `param_grid_schema`
- 已新增 `ScenarioTrainingPresetService`
- 已支援按模板保存與回載默認模型組合，持久化位置為 `paths.config/scenario_training_defaults.json`
- `ScenarioWorkflowService` 已支援接收使用者選定的訓練步驟集合
- `ScenarioTrainingDialog` 已從固定模板訓練計畫，擴充為可監控使用者選定的模型方案
- `ScenarioTrainingDialog` 已補上 task details 安全降級，測試替身與異常 task id 不會再把 UI 拉進全域例外對話框

本輪聚焦範圍：

- 先完成模型選擇、參數調整、默認保存與訓練承接
- 模型刪除保留到後續工作包

涉及檔案：

- `src/xenix/services/scenario_template_service.py`
- `src/xenix/services/scenario_training_preset_service.py`
- `src/xenix/services/scenario_workflow_service.py`
- `src/xenix/ui/scenario_training_selection_dialog.py`
- `src/xenix/ui/scenario_training_dialog.py`
- `src/xenix/ui/main_window.py`
- `src/xenix/app.py`
- `src/xenix/translations/xenix_en_US.ts`
- `src/xenix/translations/xenix_zh_CN.ts`
- `tests/test_scenario_ui.py`
- `tests/test_scenario_workflow.py`
- `tests/test_i18n.py`

驗證結果：

- `python -m compileall src tests scripts` 已通過
- 與工作包 3 直接相關的目標用例已通過，包括：
  - 模型選擇頁的默認組合保存與回載
  - 主視窗在 `TRAIN_NEW` 分支打開模型選擇頁，並將選定步驟送入訓練流程
  - `ScenarioWorkflowService` 對自訂訓練步驟集合的承接
  - `zh_CN` 下既有主流程與新增訓練頁文案切換

驗收回修：

- 日期：`2026-04-24`

本輪修復：

- 已訓練模型列表中的建立時間顯示已修正
  - 診斷結果：SQLite round-trip 後，`created_at` 在部分查詢路徑中會回到 naive datetime
  - 原先 `ScenarioModelSourceDialog` 直接 `strftime`，因此 UTC 時間會被當作本地時間直接顯示
  - 目前修正為：
    - 在 `ScenarioModelSourceService` 先將 `created_at` 正規化為 UTC-aware datetime
    - 在 UI 顯示階段統一轉換為本地時區後格式化
    - 相同格式化規則也同步套用到 `PreviousModelFlowDialog` 與 `InferenceHistoryDialog`
- `Hyperparameter Tuning` 的表單切換已修正
  - 診斷結果：`QComboBox.currentData()` 對 `StrEnum` 取回的是 plain `str`
  - 原先 `ScenarioTrainingSelectionDialog.current_operation()` 只接受 enum instance，導致操作模式會回退到 `FIT`
  - 目前修正為：
    - 將 combobox 回傳的 `str` 顯式轉回 `ScenarioTrainingOperation`
    - tuning 模式現在會正確套用 `param_grid_schema`
- `param_grid_schema` 的多值輸入形態已加強
  - `JsonSchemaFormWidget` 的 array 欄位已從單行逗號輸入，升級成多行值輸入
  - 每個候選值以一行呈現，更接近參數矩陣的互動語義
  - 舊的逗號分隔輸入仍可被解析，避免破壞既有使用習慣

本輪補充驗證：

- `tests/test_json_schema_form.py`
- `tests/test_scenario_ui.py`
  - 已覆蓋相容已訓練模型時間正規化
  - 已覆蓋 tuning 模式切換到多值輸入並輸出 list 型 `param_grid`

### 工作包 4：訓練結果視圖重寫

目標：

- 將訓練頁主視圖轉成模型結果視圖

主要工作：

- 以模型卡片替代表格中心視角
- 顯示 `MSE`、`R平方` 與提示說明
- 補上保存模型與保存狀態

實作狀態：

- 已完成第一輪落地，日期為 `2026-04-24`

本輪已完成：

- `ScenarioTrainingDialog` 的主視圖已由任務步驟表重寫為模型結果卡片列表
- 每張卡片已展示：
  - 模型名稱
  - 訓練模式
  - `R平方`
  - `MSE`
  - 其他可用評估指標
  - 參數摘要
  - 保存狀態
- 最佳模型卡片已補上顯式標記
- 模型結果卡片可切換右側的 task details 檢視
- 原本的 task details 區已保留為進階資訊區
- `ScenarioWorkflowService` 已擴充訓練步驟快照，現在會帶出：
  - 模型展示名稱
  - 訓練參數
  - 最佳參數
  - 評估指標
  - 主指標
  - 候選數量
  - 已保存模型 id
- 訓練結束摘要文案已調整為面向模型結果的語義
- 中英文翻譯資產已補齊新的模型結果視圖文案

本輪保留：

- SVG 中的顯式「保存該模型」按鈕與二次點擊鎖定規則，仍由後續模型資產工作包補齊

涉及檔案：

- `src/xenix/services/scenario_workflow_service.py`
- `src/xenix/ui/scenario_training_dialog.py`
- `src/xenix/translations/xenix_en_US.ts`
- `src/xenix/translations/xenix_zh_CN.ts`
- `tests/test_scenario_ui.py`

驗證結果：

- `python -m compileall src tests scripts` 已於前序工作包通過
- 與工作包 4 直接相關的目標用例已通過，包括：
  - 訓練頁從資料準備項啟動訓練
  - 主視窗在 `TRAIN_NEW` 分支承接訓練流程
  - 模型結果卡片顯示 `R平方`、`MSE` 與保存狀態

驗收回修：

- 日期：`2026-04-24`

本輪修正：

- 模型結果卡片的視覺語言已與現有 scenario UI 對齊
- 卡片外層樣式已限制在卡片容器本身，內容列不再呈現輸入框式邊框
- 狀態 badge、指標摘要、保存狀態與選中態已收斂成與既有 `StyledPanel` 相容的表達方式

### 工作包 5：推論頁靠攏

目標：

- 讓推論頁更接近「輸入 -> 結果」而不是「任務 -> 檔案」

主要工作：

- 補上單筆與批量的結果預覽
- 補上批次檔案前 5 筆預覽
- 支援按指定模型預測
- 補上精確的按鈕啟用條件

實作狀態：

- 已完成第一輪落地，日期為 `2026-04-24`

本輪已完成：

- `ScenarioInferenceDialog` 已從「最佳模型 + 任務表」視角，重寫為「模型選擇 + 輸入 + 結果預覽」主視圖
- 推論頁已新增模型選擇器，使用者現在可在已訓練模型之間切換，並以指定模型發起預測
- 單筆推論已補上前置完整性檢查：
  - 至少一列完整輸入後才可開始預測
  - 任何部分填寫列存在時，按鈕維持 disabled
- 批次推論已補上檔案相容性檢查與前 5 筆預覽
- 批次推論只接受包含所需輸入欄位的檔案
- 推論結果已新增直接預覽區：
  - 顯示結果前 5 筆
  - 顯示輸出欄位名稱
  - 顯示本次使用模型
- 推論活動表已保留作為進階層，仍可查看 task details 與 logs
- 新提交的推論任務現在會自動成為選中活動，結果完成後可直接回填到主視圖

涉及檔案：

- `src/xenix/ui/scenario_inference_dialog.py`
- `src/xenix/ui/widgets/inference_row_editor.py`
- `src/xenix/translations/xenix_en_US.ts`
- `src/xenix/translations/xenix_zh_CN.ts`
- `tests/test_scenario_ui.py`

驗證結果：

- 與工作包 5 直接相關的目標用例已通過，包括：
  - 單筆推論的按鈕啟用條件與結果預覽
  - 批次預覽前 5 筆
  - 指定已訓練模型發起推論

### 工作包 6：已訓練模型回用路徑

目標：

- 完成資料準備後的已訓練模型回用路徑

主要工作：

- 相容模型查詢
- 模型查詢、排序、資訊展示
- 模型確認與刪除
- 直接承接到推論

實作狀態：

- 已完成第一輪落地，日期為 `2026-04-24`

本輪已完成：

- 資料準備後選擇 `選擇已訓練模型`，現在會直接承接到 `ScenarioInferenceDialog`
- 推論頁已支援承接第二步傳入的相容模型清單
- 推論頁會預選第二步剛選中的已訓練模型
- `MLService.infer()` 已放寬成可接受跨 work item 的已訓練模型
- 跨 work item 推論目前要求：
  - 輸入列完全一致
  - 預測目標完全一致
- 已訓練模型回用路徑現在已具備：
  - 相容模型查詢
  - 最新優先排序
  - 模型資訊展示
  - 模型確認後直接進推論

本輪保留：

- SVG 中的刪除模型操作與刪除後的最佳模型重選規則，仍保留在工作包 6 的下一輪

涉及檔案：

- `src/xenix/services/ml_service.py`
- `src/xenix/services/scenario_model_source_service.py`
- `src/xenix/ui/scenario_model_source_dialog.py`
- `src/xenix/ui/scenario_inference_dialog.py`
- `src/xenix/ui/main_window.py`
- `src/xenix/translations/xenix_en_US.ts`
- `src/xenix/translations/xenix_zh_CN.ts`
- `tests/test_scenario_ui.py`

驗證結果：

- 與工作包 6 直接相關的目標用例已通過，包括：
  - 主視窗從第二步的已訓練模型分支直接打開推論頁
  - 跨 work item 已訓練模型在相容欄位配置下可直接推論

### 工作包 7：模型 metadata 與保存語義

目標：

- 讓模型保存具備 SVG 所要求的產品語義

主要工作：

- 增加模型保存說明結構
- 增加命名規則
- 增加訓練來源、欄位、樣例、評估值的持久化

## 我們真正要做的事

如果目標是讓軟體的用戶互動模式向這份 SVG 靠攏，核心工作可以濃縮成一句話：

把目前「固定模板自動訓練 + 最佳模型自動推論」的流程，重構成「場景驅動的共用流程 + 資料準備後選擇模型來源 + 模型可見可選 + 結果直讀」的流程。

最關鍵的改動集中在四個產品層：

- 首頁層：場景入口與場景目錄
- 資料後分流層：新模型訓練與已訓練模型回用
- 推論層：按模型預測與結果直讀
- 模型資產層：過往模型回用與 metadata

## 優先順序建議

若以最小可行靠攏路線來排，建議順序如下：

1. 首頁場景入口與場景目錄
2. 資料準備與模型來源分流
3. 新模型選擇與訓練模式
4. 推論頁靠攏
5. 已訓練模型回用路徑
6. 模型 metadata 完整化

這個順序可以最大化重用現有的 A -> B -> C 骨架，也能最快把整體互動模式拉近到 SVG 的語義。
