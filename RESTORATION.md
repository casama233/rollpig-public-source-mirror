# 公共災備恢復準備：先核對權利，再發布

## 本批做到哪裡

本批只加入可執行的發布授權檢查、測試及更嚴格的 Vercel notice-only 建置限制，**不恢復 `public/v1`，不啟動自動同步，不解除插件的 `PUBLIC_MIRROR_FAIL_CLOSED`**。`publication-approvals.json` 的批准清單刻意留空：目前沒有因此獲得鏡像發布授權的素材。CI 通過不等於版權審計完成。

## 候選包與審核記錄

只能評估與權威 primary 相同的已審計 base-only publication。`manifest.json` 的 `publication_profile` 必須是 `provenance-safe-base-only`。包只含 `pig.json`、基礎圖片、`manifest.json`、`NOTICE.md`、`PROVENANCE.json` 及適用的 `LICENSES/*.txt`／`*.md`。不帶 EX、烤豬文案包、相容性擴充、舊 mirror.json／health.json、憑證或私有檔案。

`PROVENANCE.json` 以 `publication_profile` 及 `files` 為頂層欄位。`files` 必須逐項覆蓋 pig.json（包括目錄文字）及每張基礎圖片；每項都要有 author、source_url、evidence_url、license_file、rights_basis、review_note 與真正經人工核驗的 redistribution_verified=true。rights_basis 只接受 original-work、explicit-permission、public-domain、permissive-asset-license；不是任填 true 就得到權利。

仓库维护的 `publication-approvals.json` 与下载包分离，不能信任镜像自带批准文件。其 approved_snapshots 用完整 manifest SHA-256 作键，每项包含 status=approved、profile、固定 primary_manifest_url、review_url 和 files（每个实际文件路径对应其 SHA-256，包含授权与来源材料）。仅有全局代码 MIT 许可、可下载、注明非商业，均不能替代逐项素材再分发依据。

审批记录、各文件、来源材料或目录任一改变，都须重新审查；缺少证据、撤销批准、换图、夹带未声明档案、symlink、路径穿越都拒绝。检查器只能证明实际字节与已记录审查一致，不能自动判断声明是否真实或授权范围是否足够。

## 仍需完成，不能跳过

1. 从有权再分发的候选资源建立真实证据，不从旧 Git 历史或旧部署恢复整包，不把 Felis 客户端直读许可当作 CDN 镜像许可。
2. 人工核验候选与权威源确为同一份发布，把审核记录、素材与授权材料绑定在同一独立 PR；删除／撤销授权时同时处理 CDN、GitHub 当前发布与客户端缓存政策。
3. 插件端加入独立的 mirror provenance contract 验证，并端到端验证主源故障、空白名单、旧快照、损坏文件与私人源隔离；之后才可在同一协调发布中解除双侧锁定。
4. 当前 sync_primary.py 是历史下载工具，不负责新的授权资料获取或审查；不能仅开启 cron 就投入服务。未来需移除其仅版本／manifest 相同就提前返回的捷径，每次验证完整当前授权候选，并在重新开放前设计撤回与失败后的清理策略。

## 本地验证

```bash
python -m unittest discover -s tests -v
python scripts/validate_snapshot.py /path/to/reviewed-candidate
```

第二条默认使用仓库内的批准清单；目前为空，所以应拒绝全部资源候选。测试使用程序临时生成的合成数据，不含第三方图片／文案，不会成为公开源。
