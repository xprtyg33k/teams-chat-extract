## Planned and Completed Improvements for `teams_chat_export.py`

### ✅ Completed Improvements

- [x] **Option 1A – Page-level pagination progress**  
  - **Status**: Completed  
  - **Date**: 2025-11-24  
  - **Description**: Added an optional `on_page` callback to the Graph pagination helper (`_paginate`) and wired it into `get_chat_messages_filtered` so that the export script reports running totals (e.g., `Retrieved X messages so far...`) as message pages are fetched from Microsoft Graph.

### 📌 Planned Improvements

- [ ] **Option 2 – Lightweight progress spinner thread**  
  - **Status**: Pending validation after Option 1A  
  - **Planned Work**: Introduce a small background spinner (e.g., using `threading.Thread`) that provides visual feedback during long-running operations such as authentication and initial message retrieval, without changing the core synchronous control flow.

- [ ] **Option 3 – Parallel exports for multiple chats (ThreadPoolExecutor)**  
  - **Status**: High priority – implement if clearly distinct from Option 4  
  - **Planned Work**: Allow exporting multiple chat IDs in a single run using `concurrent.futures.ThreadPoolExecutor`, so different chats can be exported in parallel while still streaming per-chat progress to the console. Prioritized over Option 4 unless async I/O provides clear, maintainable advantages.

- [ ] **Option 4 – Full async I/O with `aiohttp`**  
  - **Status**: Evaluate after Option 3 design  
  - **Planned Work**: Replace the synchronous `requests` layer with an async client (e.g., `aiohttp`) and provide async variants of the Graph client methods. Only implement if this approach offers compelling benefits over the ThreadPool-based approach in Option 3 (for example, significantly better scalability or cleaner concurrency semantics).

