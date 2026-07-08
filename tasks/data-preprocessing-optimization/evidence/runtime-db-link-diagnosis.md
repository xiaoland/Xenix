# Runtime DB Link Diagnosis

## Observed Failure

User clicked:

```text
artifact://eb1367a427164cf1b9bb29d18cc54df7
```

UI reported that the artifact was not found.

## Runtime Facts

- Runtime DB: `C:\Users\yyh\AppData\Local\Xenix\state\xenix.db`.
- DB `user_version`: 14.
- `eb1367a427164cf1b9bb29d18cc54df7` existed in `dataset`, not in `artifact`.
- Dataset name: `4月堂食销售数据_最终清洗版`.
- Dataset source format: Parquet.
- Dataset source path: `C:\Users\yyh\AppData\Local\Xenix\state\datasets\derived\eb1367a427164cf1b9bb29d18cc54df7.parquet`.
- The corresponding artifact row was `1adb63b6cd1249639fe01000f9cb57e7`, with metadata pointing back to the dataset id.

## Diagnosis

The assistant message used a dataset id inside an `artifact://` URI. `artifact://` correctly resolves only through `ArtifactService`, so the dataset id was reported as a missing artifact.

Secondary issue: the existing artifact pointed directly at internal app-owned Parquet. That did not satisfy the desired contract that dataset opening should lazily materialize a user-openable workbook export.

## Promoted Decisions

- `artifact://` is artifact-id authority only.
- `dataset://` is dataset-id authority and activates lazy dataset export.
- `LinkRouter` owns service-owned URI activation.
- `DatasetExportService` owns dataset activation/export.
- `ArtifactService` owns artifact file opening.
