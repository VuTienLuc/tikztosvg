# tikztosvg — TikZ → SVG Studio

[![CI · Docker](https://github.com/VuTienLuc/tikztosvg/actions/workflows/ci.yml/badge.svg)](https://github.com/VuTienLuc/tikztosvg/actions/workflows/ci.yml)

Studio chuyển mã TikZ thành **SVG tự chứa** cho bài giảng, phiếu học tập và website Toán. Chữ được chuyển thành path, nên hình không cần phông và không phụ thuộc mạng.

**Mở Studio:** https://tikztosvg.vercel.app/

Studio có hai bộ biên dịch:

| | TikZJax (sẵn trong trình duyệt) | Máy chủ LaTeX + dvisvgm |
|---|---|---|
| Cần cài | Không | Một lệnh (xem bên dưới) |
| pgfplots, tkz-euclide, tikz-cd, tkz-tab | ✗ | ✓ |
| Chữ tiếng Việt trong nhãn | ✗ | ✓ |
| Thời gian mỗi hình | 5–90 giây | khoảng 0,5 giây |

Ở chế độ **Tự động**, Studio dùng máy chủ khi kết nối được, không thì quay về TikZJax.

<a id="cai-may-chu"></a>
## Cài máy chủ

### Mac: một dòng lệnh, tự bật khi mở máy

Mở **Terminal** rồi dán:

```bash
bash -c "$(curl -fsSL https://tikztosvg.vercel.app/install-mac.sh)"
```

Bộ cài làm lần lượt các việc sau:
- Kiểm tra Python 3.
- Cài BasicTeX nếu máy chưa có TeX (cần Homebrew).
- Cài các gói pgfplots, tkz-euclide, tikz-cd, tkz-tab, vntex và dvisvgm nếu còn thiếu.
- Đăng ký máy chủ chạy nền. Từ đó mỗi lần mở máy, máy chủ tự bật tại `http://127.0.0.1:8765`.

macOS sẽ hỏi mật khẩu máy khi cài TeX hoặc gói.

- **Cập nhật** lên bản mới: chạy lại đúng lệnh trên.
- **Gỡ cài đặt:** `bash -c "$(curl -fsSL https://tikztosvg.vercel.app/uninstall-mac.sh)"`
- **Nhật ký:** `~/Library/Logs/tikz-svg-server.log`

### Docker (Windows, Linux, Mac): tự bật cùng Docker

Image được GitHub Actions build sẵn cho cả Intel và Apple Silicon:

```bash
docker run -d --name tikz-svg --restart unless-stopped -p 127.0.0.1:8765:8765 ghcr.io/vutienluc/tikz-svg-server:latest
```

Cập nhật: `docker pull ghcr.io/vutienluc/tikz-svg-server:latest`, sau đó xoá và chạy lại container.

### Cloud: dùng chung cho tổ bộ môn

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/VuTienLuc/tikztosvg)

Render tự tạo mật khẩu `API_TOKEN`, xem trong tab **Environment**. Trong Studio, dán địa chỉ `https://…onrender.com` và mật khẩu vào hai ô của thanh **Bộ biên dịch**. Render tự cập nhật mỗi khi có commit mới. Gói miễn phí "ngủ" khi không dùng, nên lần gọi đầu sau đó chậm khoảng 30 giây.

Muốn dùng Google Cloud Run thay Render: xem [server/README-cloud.md](server/README-cloud.md).

## Trình duyệt

Nên dùng **Chrome hoặc Edge**. Lần đầu trang trên Vercel gọi máy chủ trên máy thầy, Chrome có thể hỏi *"Cho phép truy cập thiết bị trong mạng cục bộ?"*: chọn **Cho phép**.

Nếu Safari chặn kết nối tới `127.0.0.1`, hãy tải `index.html` về máy và mở trực tiếp.

## Tự động hoá

Mỗi lần đẩy code lên nhánh `main`:

1. **Vercel** tự xuất bản Studio, bộ cài Mac và `server/server.py` lên https://tikztosvg.vercel.app (theo [`vercel.json`](vercel.json)).
2. **GitHub Actions** ([`ci.yml`](.github/workflows/ci.yml)) cài TeX Live và chạy thử máy chủ với hình thật: tiếng Việt, pgfplots, tkz-euclide, tikz-cd, tô màu chuyển sắc. Kiểm tra luôn việc chặn lệnh nguy hiểm và cú pháp Studio.
3. Nếu bước chạy thử đạt, GitHub Actions build image Docker (amd64 + arm64) lên `ghcr.io`.

Bước chạy thử báo đỏ trên GitHub nghĩa là bản vừa đẩy có lỗi. Khi đó hãy sửa trước khi dùng bộ cài Mac mới.

## Cấu trúc

```
index.html            Studio (một tệp HTML)
vercel.json           Cấu hình xuất bản Vercel
server/server.py      Máy chủ (Python thuần, không cần cài thư viện)
server/Dockerfile     Image Docker
install-mac.sh        Bộ cài Mac + tự chạy khi mở máy
uninstall-mac.sh      Gỡ cài đặt
render.yaml           Cấu hình triển khai Render
tests/                Kiểm thử tự động
```

## An toàn máy chủ

- Không bao giờ chạy shell-escape. LaTeX không đọc được tệp ngoài thư mục tạm.
- Các lệnh `\input`, `\write`, `\openout`, `\catcode`… bị chặn trước khi biên dịch.
- Mỗi bước bị giới hạn thời gian; dữ liệu gửi lên tối đa 400 KB.
- Mặc định máy chủ chỉ nhận kết nối từ chính máy đó (`127.0.0.1`). Khi đưa lên mạng, luôn đặt `API_TOKEN`.

Chi tiết API và biến môi trường: [server/README-cloud.md](server/README-cloud.md).
