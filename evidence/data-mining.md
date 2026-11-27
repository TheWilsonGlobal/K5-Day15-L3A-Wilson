# Đào data — cách đếm và kết quả

> Guide bước 1.2. Cách đếm (mục 1a) khoá lúc 11:36 Thứ Sáu 27/11/2026, **trước khi tải hay đọc review đầu tiên**. Nếu phải đổi cách đếm, ghi thêm dòng "đã đổi", không xoá dòng cũ.
> Repo chỉ chứa số đã tổng hợp, trích ngắn đã bỏ tên và link nguồn.

## 1. Cách đếm — viết TRƯỚC khi chạy

### 1a. Bản đang áp dụng — khoá lúc 11:36 Thứ Sáu 27/11/2026, trước khi tải hay đọc review nào

Thay cho bản 1b (viết 10:30, chưa lấy review nào theo bản đó). Lý do đổi: nhóm quyết định lấy từ App Store qua nguồn công khai của Apple để người khác chạy lại được.

**App** (kho: App Store Việt Nam, `vn`; ID tra bằng iTunes Search API ngày 27/11/2026):

| App | ID | Nhà phát hành trên kho |
|---|---|---|
| MoMo | 918751511 | ONLINE MOBILE SERVICES JOINT STOCK COMPANY |
| Techcombank Mobile | 1548623362 | VIETNAM TECHNOLOGICAL AND COMMERCIAL JOINT STOCK BANK |
| Money Lover | 486312413 | Finsify Joint Stock Company |

**Nguồn:** `https://itunes.apple.com/vn/rss/customerreviews/page=<N>/id=<APP_ID>/sortBy=mostRecent/json`, N = 1…10. Ngày xem: 27/11/2026. Script: `python evidence/fetch_reviews.py`.

**Mẫu, áp dụng giống nhau cho cả ba app, theo thứ tự:**

1. Đọc từ trang 1, review mới nhất trước.
2. Bỏ review trùng mã (`ma`).
3. Bỏ review không có chữ (trống, chỉ biểu tượng hoặc số).
4. Chỉ giữ review tiếng Việt: có ít nhất một chữ mang dấu riêng của tiếng Việt, hoặc ít nhất 2 từ Việt không dấu trong danh sách ở script.
5. Lấy **50 review mới nhất** còn lại của mỗi app (mục tiêu N = 150, tối thiểu 30). Kho trả về ít hơn thì lấy hết và ghi số thật.
6. **Không lọc theo từ khoá hay số sao.** Số review đã bỏ ở bước 2–4 được ghi ở mục 2.

**Lưu gì** (`evidence/reviews.csv`): mã review, app, kho, link nguồn, ngày xem, ngày review, số sao, trích, nhãn, người gắn, `human_verified`. **Không lưu tên, biệt danh hay đường dẫn tới người viết.**

- `trich`: tối đa 2 câu liền nhau, chép nguyên văn; bắt đầu từ câu đầu tiên có từ khoá (giao dịch, lịch sử, sao kê, chi tiêu, thu chi, thống kê, báo cáo, phân loại, tra cứu, tìm kiếm, số dư, trừ tiền), không có thì lấy 2 câu đầu; dài quá 500 ký tự thì cắt và thêm `…`. Số điện thoại, số tài khoản, email thay bằng `[đã che]`; tên người trong nội dung thay bằng `[tên]`.
- Từ khoá chỉ dùng để chọn **câu trích**, không dùng để chọn review.

**Gắn nhãn:** dùng bảng nhãn ở 1b, xét **toàn bộ tiêu đề và nội dung**. Claude gắn nhãn **nháp** (`human_verified = false`). Người trong nhóm đọc từng dòng, sửa nhãn nếu sai và đổi thành `true`. **Chỉ dòng đã kiểm mới được tính vào bằng chứng**; người thứ hai gắn nhãn độc lập 10 review (`evidence/reviews-check.csv`).

**Câu hỏi chính và mẫu số:** như 1b. Báo số gộp và số từng app. Money Lover là app ghi chép chi tiêu: chỉ tính khi review kể khó khăn xem, hiểu, tổng hợp chi tiêu của mình; lỗi đăng nhập, giá gói, quảng cáo là `khac`.

### 1b. Bản đầu (10:30) — đã thay bằng 1a, giữ lại để đối chiếu

**Nguồn và cách lấy mẫu**

- App: MoMo, ZaloPay và 1 app ngân hàng số (nhóm ghi tên app **trước khi đọc**: chưa điền; bản này đã được thay).
- Kho: Google Play (ngôn ngữ Việt, sắp theo "Mới nhất"). App nào không đủ thì lấy thêm App Store Việt Nam và ghi rõ.
- Mẫu: **15 review mới nhất có phần chữ** của mỗi app, **mọi mức sao**, tính ngược từ thời điểm lấy → N = 45 (tối thiểu 30). Không bỏ review nào vì nội dung; chỉ bỏ review trống hoặc chỉ có biểu tượng, và ghi số đã bỏ.
- Không lọc theo từ khoá. Nếu sau đó lấy thêm mẫu lọc từ khoá (sao kê, lịch sử giao dịch, chi tiêu) thì đếm **riêng**, không gộp vào N.

**Đếm gì**

- **Câu hỏi chính:** trong N review, bao nhiêu review kể khó khăn khi **xem, hiểu hoặc tổng hợp** lịch sử giao dịch, chi tiêu của chính mình.
- **Mẫu số:** toàn bộ N review đã đọc và gắn nhãn, kể cả review không liên quan.
- Một review một nhãn chính. Review khớp nhiều nhãn thì lấy nhãn đứng trên trong bảng.

**Nhãn nháp** (đọc khoảng 30 review rồi mới chốt; mọi thay đổi ghi vào mục "Đã đổi")

| Nhãn | Định nghĩa | Tính vào số chính? |
|---|---|---|
| `kho_hieu_gd` | Không hiểu một giao dịch là gì, ở đâu, vì sao bị trừ tiền | Có |
| `kho_tong_hop` | Muốn biết tổng chi, chi theo nhóm hoặc theo thời gian mà không làm được hay phải tự cộng | Có |
| `kho_tim_gd` | Khó tìm, lọc, xem lại hoặc xuất lịch sử giao dịch | Có |
| `ngan_sach` | Biết vượt ngân sách quá muộn, muốn được nhắc (hướng E2) | Đếm riêng |
| `gd_bi_chan` | Giao dịch bị tạm giữ, bị chặn, nghi lừa đảo (hướng E3) | Đếm riêng |
| `khac` | Mọi nội dung còn lại | Không |

**Bảng gắn nhãn:** `evidence/reviews.csv`, cột `ma,app,kho,link,ngay_xem,ngay_review,so_sao,trich,nhan,nguoi_gan`. `trich` tối đa 2 câu, bỏ tên người viết, số điện thoại, số tài khoản.

**Kiểm nhãn:** người thứ hai gắn nhãn độc lập 10 review, ghi số khớp x/10.

- Script / công thức: `python evidence/count.py`.

**Đã đổi** (thời điểm · đổi gì · vì sao):

- Thứ Sáu 27/11 11:36, trước khi tải review: đổi app, kho, cỡ mẫu và cách trích theo mục 1a; thêm cột `human_verified`.
- Thứ Sáu 27/11, trước khi đọc review: viết sẵn `evidence/count.py`; nhãn của người thứ hai ghi ở `evidence/reviews-check.csv` (cột `ma,nhan`). Cách lấy mẫu và cách đếm giữ nguyên.
- Thứ Sáu 27/11 buổi trưa, sau khi tải: 10 review cho người thứ hai rút ngẫu nhiên từ 150 (seed `20261127`), ghi sẵn ở `evidence/reviews-check.csv`, không kèm nhãn nháp. Phiếu chỉ có đoạn trích, nên người thứ hai thấy ít chữ hơn lúc gắn nhãn nháp; không mở `reviews.csv` hay `labels-draft.csv` trước khi điền.

## 2. Đọc trước, đếm sau

Lấy lúc 11:37 Thứ Sáu 27/11/2026 (số đếm trong `evidence/fetch-log.json`):

| App | Nguồn trả về (đã xét) | Bỏ: trùng | Bỏ: không chữ | Bỏ: không phải tiếng Việt | Giữ |
|---|---:|---:|---:|---:|---:|
| MoMo | 69 | 0 | 0 | 19 | 50 |
| Techcombank Mobile | 51 | 0 | 1 | 0 | 50 |
| Money Lover | 58 | 0 | 1 | 7 | 50 |

Ghi chú của Claude sau khi đọc 150 review (**nháp, chờ người đọc lại**):

- Giữ nguyên bảng nhãn ở 1b, không thêm nhãn.
- Phần lớn không liên quan: khen chung, lỗi chuyển khoản, lỗi phiên bản iOS, quảng cáo, giá gói.
- Trong nhóm `kho_hieu_gd`, nhiều review là **bức xúc vì bị trừ phí hoặc trừ tiền bất ngờ**, không phải đọc không hiểu mô tả viết tắt như giả thuyết. Người kiểm cần quyết có tính loại này không, và áp dụng cùng một cách cho mọi dòng.
- Bộ lọc tiếng Việt có thể đã bỏ cả review ngắn viết không dấu (chỉ một từ Việt nhận ra được).

## 3. Kết quả

> **NHÁP, CHƯA PHẢI BẰNG CHỨNG.** Nhãn do Claude gắn, người chưa kiểm dòng nào (0/150). Số chính thức lấy từ `python evidence/count.py` sau khi kiểm.

| Đếm gì | Nháp (nhãn máy) | Sau khi người kiểm |
|---|---|---|
| Khó xem, hiểu, tổng hợp giao dịch (3 nhãn chính) | 11/150 (7%) | [CHỜ DỮ LIỆU THẬT] |
| – trong đó `kho_hieu_gd` · `kho_tong_hop` · `kho_tim_gd` | 8 · 1 · 2 | [CHỜ DỮ LIỆU THẬT] |
| – theo app: MoMo · Techcombank Mobile · Money Lover | 3/50 · 6/50 · 2/50 | [CHỜ DỮ LIỆU THẬT] |
| Cảnh báo ngân sách (`ngan_sach`, hướng E2) | 1/150 | [CHỜ DỮ LIỆU THẬT] |
| Giao dịch bị chặn (`gd_bi_chan`, hướng E3) | 0/150 | [CHỜ DỮ LIỆU THẬT] |
| Người thứ hai gắn nhãn khớp | — | [CHỜ DỮ LIỆU THẬT: x/10] |

## 4. ≥5 ví dụ cụ thể (mã review, đã bỏ tên)

Nhãn nháp; [CHỜ DỮ LIỆU THẬT: người kiểm xác nhận từng ví dụ]. Trích nguyên văn; link nguồn và ngày xem của từng mã ở `evidence/reviews.csv`.

| Mã | App | Ngày review | Nhãn nháp | Trích |
|---|---|---|---|---|
| `14827102118` | Techcombank Mobile | 2026-11-23 | kho_tong_hop | "Lược bỏ biểu đồ thu chi hàng tháng" |
| `14807101798` | Techcombank Mobile | 2026-11-18 | kho_hieu_gd | "Sao kê thẻ charge 2 lần tiền, gọi tổng đài bận, email không phản hồi, vài ngày sau lên kiểm tra thì đã tự ý chỉnh sửa" |
| `14830552939` | Techcombank Mobile | 2026-11-24 | kho_hieu_gd | "Thẻ tín dụng mình chưa từng sử dụng đột nhiên lại bị trừ tiền phí thường niên mà bản thân mình còn chưa hề kích hoạt nó lên trên app bây giờ lại bị trừ phí oan uổng ngay từ đầu lại không nói rõ ràng về phí thường niên luôn nói là thẻ thì miễn phí cho người dùng lâu năm nên mình mới đồng ý lấy thẻ để sử dụng cho kế hoạch sau này. Bây giờ còn chưa kích hoạt thẻ lên lại bị trừ phí thường niên khó hiểu ấy thật sự tự nhiên thấy thông báo sao kê làm mình ngờ ngợ, ngân hàng làm ăn khó hiểu" |
| `14826930912` | Techcombank Mobile | 2026-11-23 | kho_hieu_gd | "Lúc chào hàng mở không nói gì tới giờ nộp tiền vào trừ hết 132k của sinh viên cuối tháng rồi xoay sở sao :)))" |
| `14805495226` | Techcombank Mobile | 2026-11-18 | kho_hieu_gd | "Nhập mã giới thiệu vào tự nhiên ngân hàng tôi bị rút luôn 20k ?" |
| `14831470315` | MoMo | 2026-11-24 | kho_hieu_gd | "ko hiểu kiểu j có nợ ví momo đâu mà h thành nợ mà tiền thì ko thấy đâu ?" |
| `14618149831` | Money Lover | 2026-10-02 | kho_tim_gd | "Mất tiền mất lịch sử giao dịch đã ghi ra" |

## 5. Giới hạn của data

- Nguồn RSS của Apple chỉ trả một số review gần nhất; chạy lại ngày khác sẽ ra mẫu khác. Mẫu đã lấy được giữ trong `evidence/reviews.csv`.
- 50 review mới nhất trải trên khoảng thời gian rất khác nhau: MoMo 24–25/11/2026, Techcombank Mobile 18–25/11/2026, Money Lover 19/03–24/11/2026. Hai app đầu chịu ảnh hưởng của sự cố trong tuần đó (vd lỗi chuyển khoản trên bản iOS mới).
- Chỉ có người dùng iPhone ở kho Việt Nam. Người dùng Money Lover vốn đã chủ động theo dõi chi tiêu, không đại diện người dùng chung.
- Người viết review thường đang bực, nên % trong review không phải % của mọi người dùng.
- Review app thiên về lỗi đăng nhập, chuyển tiền; khó khăn khi tổng hợp chi tiêu có thể ít được viết ra.
- Review không cho biết người viết có đúng vai người dùng chính hay không.

→ Kiểm lại bằng phỏng vấn (`evidence/interviews/`).
