# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Doanh nghiệp SME tại Nhật Bản, Hàn Quốc, châu Âu cần outsourcing web, mobile, backend, cloud (trang chủ hiện tại).
- Phụ huynh sử dụng ứng dụng Kids Care (giám sát con, gán việc, vùng an toàn) — hiện diện dưới dạng case study trên trang chủ.

## Product Purpose

Cross Tech Edu là đội kỹ thuật đặt tại Việt Nam, nhận outsourcing web/mobile/backend/cloud với bàn giao theo sprint 2 tuần và hợp đồng không ràng buộc thời hạn; đồng thời phát triển các sản phẩm app nội bộ (GPLX, Kids Care). Trang chủ crosstechedu.com là landing page thu hút khách hàng outsourcing, đồng thời minh họa năng lực qua case studies.

## Positioning

Đội kỹ thuật tại Việt Nam, bàn giao theo sprint 2 tuần, PM và QA đi kèm miễn phí từ 3 dev, hủy hợp đồng báo trước 15 ngày — mức khởi điểm 6 triệu đ/dev/tháng, bảo hành 12 tháng.

## Operating Context

Website Flask + Jinja2, nội dung JSON under `content/`, xuất tĩnh bằng Frozen-Flask lên `build/`, deploy Vercel. Zero client-side JS. Styling hand-written CSS (`tokens.css`, `site.css`, `fonts.css`), font Archivo tự host. Màu nhấn `#ec3013`.

## Capabilities and Constraints

- Trang chủ được cấu trúc bằng content blocks JSON (`hero`, `services`, `pricing`, `products`, `client_logos`, `process`, `contact`).
- Block `products` hỗ trợ thẻ lật (App Store ↔ Google Play) với icon, cover, tên cửa hàng, URL.
- Không thêm framework JS mới; không sửa logic trang hiện có.
- Ảnh marketing Kids Care có sẵn tại `D:/projects/kids_care/docs/store/screenshots/marketing/` (6 ảnh, 1080×1920).

## Brand Commitments

- Tên: Cross Tech Edu (CROSS TECH EDU). Màu nhấn `#ec3013` (đỏ cam), nền `#f3f2f2`, chữ `#201e1d`. Font Archivo (tự host woff2).
- Email liên hệ thực: `crosstechedu@gmail.com`. Điện thoại: `+84 338 305 895`. Văn phòng Hà Nội.

## Evidence on Hand

- 6 ảnh marketing Kids Care (play-01 → play-06, nền cam, mockup điện thoại) đã copy vào `app/static/img/products/kids-care/`.
- Repo mobile GPLX (`D:/projects/gplx`) xác nhận package `com.crosstechedu.gplx`.

## Product Principles

1. Không sửa giao diện hoặc logic các trang hiện có nếu không cần thiết.
2. Tận dụng tài nguyên và block có sẵn; không tạo framework/thư viện mới.
3. Mọi link phải trỏ đến tài nguyên thật; không bịa email, không bịa link store chưa xác thực.
4. Responsive trên điện thoại và desktop; SEO cơ bản (title, description, heading, canonical).

## Accessibility & Inclusion

Tuân thủ mức truy cập hiện có của trang (focus-visible, alt text trên ảnh, aria-label trên section). Không yêu cầu thêm standard mới ngoài trang chủ hiện tại.
