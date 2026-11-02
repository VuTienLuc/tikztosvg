# Máy chủ TikZ → SVG: API, biến môi trường, triển khai cloud

## Chạy tay

```bash
python3 server/server.py          # cần latex + dvisvgm trong PATH
```

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `PORT` | `8765` | Cổng (Render và Cloud Run tự đặt biến này) |
| `HOST` | `127.0.0.1` (Docker: `0.0.0.0`) | Địa chỉ lắng nghe |
| `API_TOKEN` | (trống) | Nếu đặt, yêu cầu phải gửi header `X-Token` khớp |
| `ALLOW_ORIGIN` | `*` | Trang được gọi máy chủ; có thể đặt `https://vutienluc.github.io` |
| `MAX_JOBS` | `2` | Số hình biên dịch song song |
| `TIMEOUT` | `40` | Số giây tối đa mỗi bước latex/dvisvgm |

## Google Cloud Run

```bash
gcloud run deploy tikz-svg --source server --region asia-southeast1 \
  --allow-unauthenticated --memory 1Gi \
  --set-env-vars API_TOKEN=mat-khau-dai-kho-doan,ALLOW_ORIGIN=https://vutienluc.github.io
```

Cách khác là chạy thẳng image đã build sẵn: `--image ghcr.io/vutienluc/tikz-svg-server:latest`. Cloud Run chỉ nhận image từ một số kho, nên có thể cần sao chép image sang Artifact Registry trước.

## API

- `GET /health` trả về `{ok, dvisvgm, vietnamese, token, packages:{…}}`.
- `POST /compile` (header `X-Token` nếu có đặt `API_TOKEN`):
  ```json
  {"body": "\\begin{tikzpicture}…\\end{tikzpicture}",
   "preamble": "\\tikzset{…}",
   "packages": [{"name": "tkz-euclide", "opts": ""}]}
  ```
  - Thành công: `200 {svg, ms, cached}`.
  - Lỗi TeX hoặc mã bị chặn: `422 {error}`.
  - Sai mã truy cập: `401`.

Máy chủ ghép tài liệu `standalone` dùng driver `pgfsys-dvisvgm`, có sẵn amsmath, các thư viện TikZ hay dùng và T5 cho tiếng Việt. Sau đó chạy `latex -no-shell-escape` rồi `dvisvgm --no-fonts=1 --exact-bbox --optimize`, và đổi `style="…"` thành thuộc tính rời để SVG tự chứa.
