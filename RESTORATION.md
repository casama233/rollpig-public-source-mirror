# 公共災備恢復準備

## 狀態

本批只有離線驗證器與 notice-only 建置限制，**沒有恢復 public/v1、沒有開 cron、沒有解除插件 PUBLIC_MIRROR_FAIL_CLOSED**。publication-approvals.json 的批准清單仍為空。通過程式測試不是素材獲得授權，也不是鏡像已上線。

## 與權威服務的實際格式對齊

契約基準：rollpig-public-source-service 的 build_provenance_safe_source.py 與 build_resource_source.py，提交 8e5d1d6c8b67c478896d5b5213b1b1f6e784de80。

- manifest 使用 `profile=provenance-safe-base-only`，不是 `publication_profile`。
- `notice`、`provenance`、`licenses` 都是帶 path／size／sha256 的 manifest 成員，必須計入 `package_size`。
- `PROVENANCE.json` 使用 `resource_count` 和逐豬 `items`（id、source、classification）；不得為迎合鏡像而改寫已審核來源文件。
- 服務端可另產生 health.json；它不計入 package_size，但若帶入候選，仍須逐位元組列入獨立批准清單，且其版本、數量、profile、時間、來源及 base-only 狀態必須與 manifest 相符。
- 目錄、圖片、provenance 的 ID 集合須完全一致。EX、variant_images、roast_copy、相容性擴充、舊 mirror.json 或額外私有檔案一律不在此契約內。

一般來源服務的新 EX authoring／Release 程式，不能直接被當成 base-only 鏡像。服務程式已合併、authoring 批准或投稿審核成功，也不能替代鏡像的獨立發布批准。不要從目前可能含 EX 的 v1 偷改 profile 或刪掉幾個欄位，便宣稱是同一份已批准發布。

## 獨立批准清單 v2

批准文件在倉庫維護，不能從下載包取得。頂層 `schema_version=2`，`approved_snapshots` 以完整 manifest SHA-256 為鍵；每條記錄必須包含：

| 欄位 | 用途 |
| --- | --- |
| status | 必須是 approved；pending、revoked、not_published 都拒絕 |
| profile | 固定 provenance-safe-base-only |
| primary_manifest_url | 固定權威源地址，不接受任意私人來源 |
| review_url | 可核查的 HTTPS 發布審核記錄 |
| files | 全部實際檔案路径 → SHA-256，包含 manifest、來源材料、授權檔與可選 health |
| rights | pig.json 和每張圖片路径 → 獨立的逐檔權利審核 |

rights 每項包含 author、source_url、evidence_url、license_file、rights_basis、review_note、redistribution_verified=true。rights_basis 支持 original-work、explicit-permission、public-domain、permissive-asset-license；license_file 必須是 manifest 中的授權檔。pig.json 的審核必須涵蓋其目錄文字，不只是圖片。

來源材料的 classification 是描述，不是授權；獨立 rights 審核不能省略。檢查器只能證明實際字節、契約與記錄一致，不能判斷聲明真偽或代替人工法律／權利審核。不能僅憑代碼 MIT 授權、非商業用途、可下載或客户端直讀權限就批准 CDN 再分發。

舊的假設性 publication_profile／provenance.files 形狀不再被接受。本次升至批准清單 v2 沒有遷移任何真實批准，因為舊清單原本也是空的。

## 仍不能跳過的恢復前置條件

1. 以相同、已審核的權威 base-only 候選及真實來源／權利證據建立獨立發布 PR。不復活舊歷史快照，不以 EX 寫作批准代替公開分發批准。
2. 明確核對候選與權威發布完全一致，記錄可核驗版本與逐檔雜湊；授權撤回時，需協調 CDN、GitHub 當前發布及客戶端快取政策。
3. 客戶端實作獨立 provenance contract，完成主源故障、過期／未批准快照、檔案損壞、撤回及私人源隔離的端到端測試，才可協調解除雙側封鎖。
4. 舊 sync_primary.py 仍不是投產同步器，不能直接開啟 cron。新離線驗證不依賴它，也不執行其網路下載或版本捷徑；未來同步器必須獲取完整來源材料、每次核驗目前批准並處理撤回與失敗清理。

## 驗證

```bash
python -m unittest discover -s tests -v
python scripts/validate_snapshot.py /path/to/reviewed-candidate
```

第二條僅讀取本機候選與倉庫批准清單，不上網、不改候選、不建立發布目錄。清單為空時拒絕所有真實候選是正確結果。測試只使用合成資料，覆蓋服務端格式、完整性與拒絕路徑，不是實際素材審核或生產容災演練。
