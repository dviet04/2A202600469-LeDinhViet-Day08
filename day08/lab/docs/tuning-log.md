# Tuning Log — RAG Pipeline (Day 08 Lab)

> Template: Ghi lại mỗi thay đổi và kết quả quan sát được.  
> A/B Rule: Chỉ đổi MỘT biến mỗi lần.

---

## Baseline (Sprint 2)

**Ngày:** 2026-04-13  

**Config:**
```
retrieval_mode = "dense"
chunk_size = 500 tokens
overlap = 50 tokens
top_k_search = 10
top_k_select = 3
use_rerank = False
llm_model = gpt-4o-mini
```

**Scorecard Baseline:**
| Metric | Average Score |
|--------|--------------|
| Faithfulness | 5.00 /5 |
| Answer Relevance | 4.60 /5 |
| Context Recall | 4.90 /5 |
| Completeness | 4.00 /5 |

---

**Câu hỏi yếu nhất (điểm thấp):**

- **gq05 (Access Control)**  
  Relevance = 1, Completeness = 1.  
  Đây là lỗi nặng nhất trong baseline. Hệ thống trả lời theo hướng “không đủ dữ liệu”, trong khi bộ câu hỏi kỳ vọng phải có câu trả lời cụ thể. Như vậy pipeline không bị lỗi hallucination, mà bị lỗi **trả lời sai kiểu**: thay vì dùng evidence đã retrieve để trả lời, model chọn từ chối. Điều này làm mất cả relevance lẫn completeness.

- **gq01 (SLA)**  
  Completeness = 3.  
  Câu trả lời đúng ý chính nhưng chưa nêu đầy đủ các điều kiện hoặc chi tiết liên quan đến thay đổi SLA. Lỗi ở đây không phải sai fact, mà là **thiếu độ đầy đủ**: model chọn câu trả lời ngắn, bỏ bớt phần phụ nhưng vẫn quan trọng với người dùng.

- **gq02 (Cross-Document)**  
  Completeness = 3.  
  Đây là dạng câu hỏi cần tổng hợp từ nhiều nguồn/chunk. Baseline dense retrieval vẫn lấy được context đủ để trả lời đúng phần chính, nhưng model chưa ghép hết các ý quan trọng từ nhiều đoạn khác nhau. Lỗi này cho thấy pipeline còn yếu ở **multi-chunk synthesis**.

---

**Giả thuyết nguyên nhân (Error Tree):**

- [x] **Retrieval: Dense retrieval chưa tối ưu cho câu hỏi cần mở rộng ngữ nghĩa**  
  Các câu như gq02 cho thấy dense retrieval lấy được fact chính nhưng chưa đủ breadth để cover toàn bộ answer. Vấn đề không phải “không tìm được gì”, mà là **retrieve chưa đủ đa dạng thông tin**.

- [x] **Generation: Prompt chưa ép model trả lời đầy đủ theo tất cả điều kiện**  
  Đây là lỗi rõ nhất trong baseline. Model thường trả lời ngắn gọn, ưu tiên fact chính, nhưng bỏ qua exception, điều kiện, hoặc bước follow-up. Kết quả là faithfulness vẫn 5 nhưng completeness giảm.

- [x] **Scoring/Evaluation: Completeness phản ánh chất lượng thật, nhưng chưa tách rõ lỗi retrieval và lỗi generation**  
  Một câu completeness thấp có thể do retrieve thiếu chunk hoặc do model không dùng hết chunk đã có. Với baseline hiện tại, nhiều dấu hiệu cho thấy vấn đề lớn hơn nằm ở generation hơn là retrieval thuần túy.

---

## Variant 1 (Sprint 3)

**Ngày:** 2026-04-13  

**Biến thay đổi:** query_transform_strategy


**Lý do chọn biến này:**  
Baseline cho thấy vấn đề lớn nhất không nằm ở faithfulness mà nằm ở completeness. Nói cách khác, hệ thống thường trả lời đúng nhưng chưa đủ. Vì vậy biến hợp lý nhất để thử đầu tiên là **query expansion** nhằm mở rộng retrieval coverage, đặc biệt cho các câu hỏi cần paraphrase, semantic match, hoặc tổng hợp nhiều ý từ nhiều đoạn.

**Config:**
```
retrieval_mode = "dense"
top_k_search = 20
top_k_select = 3
use_rerank = False
query_transform_strategy = "expansion"
```

**Scorecard Variant 1:**
| Metric | Baseline | Variant 1 | Delta |
|--------|----------|-----------|-------|
| Faithfulness | 5.00 | 5.00 | +0.00 |
| Answer Relevance | 4.60 | 4.60 | +0.00 |
| Context Recall | 4.90 | 4.90 | +0.00 |
| Completeness | 4.00 | 4.10 | +0.10 |

---

**Nhận xét:**

- Variant này cải thiện đúng chỗ cần cải thiện nhất: **completeness**.  
  Điểm completeness tăng từ 4.00 lên 4.10, trong khi ba metric còn lại giữ nguyên. Đây là tín hiệu tốt vì query expansion giúp lấy thêm context hỗ trợ mà không làm model bịa thêm thông tin.

- Các câu hỏi dạng cross-document hưởng lợi nhiều hơn.  
  Với những câu cần ghép nhiều ý, query expansion làm tăng cơ hội retrieve được các chunk bổ sung, từ đó model có cơ sở để trả lời đầy đủ hơn.

- **gq05 vẫn không cải thiện đáng kể.**  
  Điều này rất quan trọng vì nó cho thấy lỗi của gq05 không chỉ nằm ở retrieval. Dù mở rộng query, model vẫn có xu hướng abstain sai. Như vậy bottleneck chính của câu này là **generation behavior**, không phải chỉ là thiếu evidence.

- Không có regression rõ ràng ở faithfulness, relevance, hay recall.  
  Đây là điểm mạnh nhất của Variant 1: cải thiện chất lượng mà không đánh đổi độ an toàn.

---

**Kết luận:**

→ Variant 1 **tốt hơn baseline**.

**Bằng chứng:**
- Completeness tăng từ **4.00 lên 4.10**
- Faithfulness giữ nguyên ở **5.00**
- Answer Relevance giữ nguyên ở **4.60**
- Context Recall giữ nguyên ở **4.90**

Kết quả này cho thấy query expansion là thay đổi có ích và ổn định nhất trong các thử nghiệm hiện tại. Vì vậy, đây là lựa chọn hợp lý để dùng làm **final variant**.

---

## Variant 2

**Biến thay đổi:** use_rerank  

**Config:**
```
retrieval_mode = "dense"
top_k_search = 10
top_k_select = 3
use_rerank = True
query_transform_strategy = None
```


**Scorecard Variant 2:**
| Metric | Baseline | Variant 2 | Delta |
|--------|----------|-----------|-------|
| Faithfulness | 5.00 | 5.00 | +0.00 |
| Answer Relevance | 4.60 | 4.50 | -0.10 |
| Context Recall | 4.90 | 4.90 | +0.00 |
| Completeness | 4.00 | 4.14 | +0.14 |


---

**Nhận xét:**

- Completeness tăng nhẹ (+0.14)  
- Relevance giảm (-0.10) → có noise từ keyword match  
- Không cải thiện câu khó (gq05 vẫn fail)  

---

**Kết luận:**

→ Hybrid giúp tăng recall nhưng giảm precision  
→ Không phải bottleneck chính  

---


**Scorecard Variant 2:**
| Metric | Baseline | Variant 1 | Variant 2 | Best |
|--------|----------|-----------|-----------|------|
| Faithfulness | 5.00 | 5.00 | 5.00 | All |
| Answer Relevance | 4.60 | 4.60 | 4.50 | Baseline / Variant 1 |
| Context Recall | 4.90 | 4.90 | 4.90 | All |
| Completeness | 4.00 | 4.10 | 4.20* | Variant 2* |

*Note: Kết quả completeness của Variant 2 có một phần không ổn định vì nhiều ô scoring bị `None/NaN`, nên con số 4.20 cần được diễn giải cẩn thận.

---

## Variant 3 — Hybrid Retrieval

**Biến thay đổi:** retrieval_mode

**Config:**
```
retrieval_mode = "hybrid"
top_k_search = 10
top_k_select = 3
use_rerank = False
query_transform_strategy = None
```



**Nhận xét:**

- Về lý thuyết, rerank nên giúp chọn đúng chunk hơn trong top candidates. Điều này phù hợp với việc completeness tăng lên 4.20.
- Tuy nhiên, answer relevance lại giảm nhẹ từ 4.60 xuống 4.50. Điều này cho thấy rerank không cải thiện đồng đều trên mọi câu hỏi.
- Quan trọng hơn, Variant 2 có dấu hiệu **scoring không ổn định**. Một số hàng completeness bị `None`, nghĩa là LLM judge hoặc parser JSON trong `eval.py` không luôn trả kết quả hợp lệ. 

---

## Tóm tắt học được

**1. Lỗi phổ biến nhất trong pipeline này là gì?**  
Lỗi phổ biến nhất không phải là hallucination mà là **incomplete answer** và **wrong abstention**. Hệ thống thường bám đúng context nên faithfulness rất cao, nhưng lại hay trả lời thiếu điều kiện hoặc từ chối trả lời trong khi đáng ra phải trả lời được.

**2. Biến nào có tác động lớn nhất tới chất lượng?**  
Biến có tác động rõ nhất và đáng tin nhất là **query expansion**. Nó cải thiện completeness mà không làm giảm faithfulness, relevance, hay recall.

**3. Nếu có thêm 1 giờ, nhóm sẽ thử gì tiếp theo?**  
- Sửa prompt generation để ép model trả lời đủ các điều kiện quan trọng, thay vì chỉ nêu ý chính.  
- Giảm lỗi wrong abstention bằng cách yêu cầu model chỉ abstain khi thật sự không có evidence.  
- Kết hợp **expansion + rerank** trong một thử nghiệm tiếp theo, nhưng cần làm sau khi đã sửa evaluation để tránh kết quả nhiễu.  
- Làm cho LLM judge ổn định hơn, đặc biệt ở phần completeness, để không còn lỗi `None/NaN`.

---

## Ghi chú kỹ thuật về evaluation code

Từ `eval.py`, có hai vấn đề kỹ thuật cần lưu ý khi đọc kết quả:

1. **LLM-as-judge có thể trả JSON không ổn định**  
   Các hàm như `score_completeness()` dùng model để trả về JSON, nhưng nếu output không parse được thì score sẽ thành `None`. Điều này làm average của một số variant kém tin cậy.

2. **So sánh delta trong `compare_ab()` cần cẩn thận với giá trị falsy**  
   Đoạn code:
   ```python
   delta = (v_avg - b_avg) if (b_avg and v_avg) else None
   b_str = f"{b_avg:.2f}" if b_avg else "N/A"
   v_str = f"{v_avg:.2f}" if v_avg else "N/A"
   d_str = f"{delta:+.2f}" if delta else "N/A"
   ```
   dùng kiểm tra truthy/falsy thay vì kiểm tra `is not None`. Cách viết này dễ gây hiển thị sai nếu một metric bằng `0.0`. Với bộ này chưa gây lỗi lớn, nhưng về mặt code quality thì nên sửa.
