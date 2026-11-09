# Flytex Camera

Camera 4G chạy pin cho ngoài trời: phát hiện chuyển động, ghi hình cục bộ, xem trực tiếp qua 4G, ngủ sâu và nhận lệnh từ xa.

Đây là phiên bản **tiền thương mại**: đủ đơn giản để dựng prototype nhanh, nhưng các giao diện (connector, rail nguồn, giao thức MCU↔SoC, cơ khí) được chốt sao cho lên production không phải làm lại.

Repo này **làm lại từ đầu**. Nó kế thừa *bài học* từ dự án CAM4G ([xuanvuong1702/camera-4G](https://github.com/xuanvuong1702/camera-4G)), không kế thừa file thiết kế nào của dự án đó.

## Trạng thái

| Hạng mục | Trạng thái |
|---|---|
| Tài liệu thiết kế | Dự thảo v0.1 (repo này) |
| Phần cứng | Chưa có, chưa vẽ schematic |
| Firmware / cloud | Chưa bắt đầu |
| Số đo thực | Chưa có. Mọi con số công suất, nhiệt, thời gian chạy đều là ước tính |

## Quyết định đã chốt

| # | Quyết định |
|---|---|
| 1 | Làm lại từ đầu, tài liệu nằm trong repo này |
| 2 | Pin: **pack 1S LFP có sẵn BMS** (không tự ghép cell rời) |
| 3 | Sạc bằng **USB-C 5 V** |

Các quyết định còn lại đều ở trạng thái *đề xuất* hoặc *mở*, xem [nhật ký quyết định](docs/11-nhat-ky-quyet-dinh.md).

## Hướng thiết kế trong một đoạn

Tách sản phẩm thành ba phần theo mức rủi ro: **board nguồn (PWR)**, **board compute (CMP)** và **breakout modem (MDM)**, nối bằng giao diện đã chốt. Dùng module OEM cho phần khó (SoC Core1106, modem EC200U-EU, camera có IR tích hợp). Đo trên dev board trước khi vẽ board nào. Mỗi lần đặt board chỉ đổi một board, và mọi footprint tự tạo phải qua board thử footprint trước.

## Nguyên tắc làm việc

1. **Đo trước, chốt sau.** Số liệu là ước tính cho đến khi có phép đo.
2. **Giảm số thứ phải tự thiết kế.** Phần khó dùng module OEM.
3. **Chốt giao diện, không chốt hiện thực.** Đổi bên trong một board không được làm đổi board khác.
4. **Mỗi con số chỉ có một nguồn sự thật.** Các tài liệu khác chỉ trỏ tới, không chép lại.
5. **Không đoán chân IC hay footprint.** Đối chiếu datasheet và kiểm bằng linh kiện thật.
6. **Không tuyên bố "chạy được" khi chưa có phép đo.**

## Nhãn dùng trong tài liệu

| Nhãn | Ý nghĩa |
|---|---|
| `[ĐÃ CHỐT]` | Chủ dự án đã quyết định |
| `[ĐỀ XUẤT]` | Khuyến nghị thiết kế, chờ xác nhận |
| `[ƯỚC TÍNH]` | Con số chưa đo |
| `[CHƯA XÁC MINH]` | Cần kiểm datasheet hoặc thử thực tế |
| `[KẾ THỪA]` | Lấy từ CAM4G, cần xác nhận lại cho dự án này |

## Mục lục

| File | Nội dung |
|---|---|
| [00-yeu-cau.md](docs/00-yeu-cau.md) | Yêu cầu, ngoài phạm vi, giả định |
| [01-kien-truc.md](docs/01-kien-truc.md) | Kiến trúc hệ thống, ba phần, trạng thái nguồn |
| [02-thiet-ke-nguon.md](docs/02-thiet-ke-nguon.md) | Pin, sạc USB-C, boost/buck, ngân sách năng lượng |
| [03-giao-dien.md](docs/03-giao-dien.md) | Rail, connector, tín hiệu giữa các board, thanh ghi I2C |
| [04-firmware.md](docs/04-firmware.md) | Firmware MCU và ứng dụng Linux |
| [05-ket-noi-va-cloud.md](docs/05-ket-noi-va-cloud.md) | Modem, mạng, cloud, xem trực tiếp |
| [06-co-khi-nhiet.md](docs/06-co-khi-nhiet.md) | Vỏ, nhiệt, ăng-ten, cổng USB-C ngoài trời |
| [07-ke-hoach-phat-trien.md](docs/07-ke-hoach-phat-trien.md) | Các giai đoạn và cổng kiểm soát |
| [08-kiem-chung.md](docs/08-kiem-chung.md) | Kế hoạch đo và kiểm tra |
| [09-san-xuat.md](docs/09-san-xuat.md) | DFM, DFT, chứng nhận, chuỗi cung ứng |
| [10-rui-ro.md](docs/10-rui-ro.md) | Sổ rủi ro |
| [11-nhat-ky-quyet-dinh.md](docs/11-nhat-ky-quyet-dinh.md) | Quyết định đã chốt, đề xuất và câu hỏi mở |
| [12-bai-hoc-tu-cam4g.md](docs/12-bai-hoc-tu-cam4g.md) | Bài học rút ra từ dự án CAM4G |
