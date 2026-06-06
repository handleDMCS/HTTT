#!/usr/bin/env python3
"""Generate the Book Exchange Club system design report artifacts."""

from __future__ import annotations

import html
import json
import re
import subprocess
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs"
ASSET_DIR = OUT_DIR / "report_assets"
DIAGRAM_SRC_DIR = ASSET_DIR / "diagrams" / "src"
DIAGRAM_RENDERED_DIR = ASSET_DIR / "diagrams" / "rendered"
PNG_RENDERER = ASSET_DIR / "render_diagrams_png.ps1"
REPORT_MD = OUT_DIR / "book_exchange_system_design_report.md"
REPORT_DOCX = OUT_DIR / "book_exchange_system_design_report.docx"
REPORT_IMAGE_EXTENSION = "svg"


DIAGRAMS = {
    "use_case_overview.mmd": """%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eff6ff", "primaryBorderColor": "#1d4ed8", "lineColor": "#0f172a", "fontFamily": "Arial"}, "flowchart": {"curve": "basis", "nodeSpacing": 44, "rankSpacing": 60}}}%%
flowchart LR
    Owner[Owner - chu so huu sach]
    Requester[Requester - nguoi nhan/muon sach]
    Courier[Courier - nguoi giao sach mien phi]

    subgraph System[Book Exchange Club]
        direction TB
        UC1((Tai khoan va ho so))
        UC2((Tim kiem va loc sach))
        UC3((Dang / sua / xoa sach))
        UC4((Chap nhan requester / courier))
        UC5((Xoa nguoi tham gia))
        UC6((Renew sach cho muon))
        UC7((Ung tuyen nhan / muon sach))
        UC8((Rut don ung tuyen))
        UC9((Chat va thong bao))
        UC10((Xac nhan giao nhan))
        UC11((Ung tuyen giao sach))
        UC12((Nhan va giao sach))
    end

    Owner --> UC1
    Owner --> UC2
    Owner --> UC3
    Owner --> UC4
    Owner --> UC5
    Owner --> UC6
    Owner --> UC9
    Owner --> UC10

    Requester --> UC1
    Requester --> UC2
    Requester --> UC7
    Requester --> UC8
    Requester --> UC9
    Requester --> UC10

    Courier --> UC1
    Courier --> UC9
    Courier --> UC10
    Courier --> UC11
    Courier --> UC12

    classDef actor fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827;
    classDef usecase fill:#eff6ff,stroke:#1d4ed8,stroke-width:2px,color:#111827;
    class Owner,Requester,Courier actor;
    class UC1,UC2,UC3,UC4,UC5,UC6,UC7,UC8,UC9,UC10,UC11,UC12 usecase;
    style System fill:#f8fafc,stroke:#334155,stroke-width:2px,color:#111827
""",
    "architecture.mmd": """flowchart LR
    Browser[Trinh duyet nguoi dung]
    LocalStorage[(localStorage\\nhttt_token + httt_member)]
    Svelte[SvelteKit 5 Frontend\\nVite + TypeScript]
    API[FastAPI Backend\\nbackend/main.py]
    SQLite[(SQLite db.sqlite3)]
    Pic[(Thu muc pic/)]
    Avatar[(Thu muc avatar/)]

    Browser --> Svelte
    Svelte <--> Browser
    Browser <--> LocalStorage
    Svelte -- REST API --> API
    API -- JSON --> Svelte
    API <--> SQLite
    API --> Pic
    API --> Avatar
    Browser -- /pic/* va /avatar/* --> API
""",
    "dfd_context.mmd": """%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#dbeafe", "primaryBorderColor": "#1d4ed8", "lineColor": "#0f172a", "fontFamily": "Arial"}, "flowchart": {"curve": "basis", "nodeSpacing": 70, "rankSpacing": 95}}}%%
flowchart LR
    Member[Thanh vien cau lac bo]
    Deliverer[Nguoi giao sach mien phi]
    System((He thong Book Exchange Club))
    Store[(Du lieu thanh vien, sach, giao dich, tin nhan)]

    Member -- du lieu tai khoan, sach, ung tuyen, chat --> System
    Deliverer -- Don xin giao sach, xac nhan giao nhan --> System
    System -- danh sach sach, trang thai, thong bao, diem --> Member
    System -- nhiem vu giao sach, thong bao, diem thuong --> Deliverer
    System <-->|doc ghi trang thai| Store

    classDef actor fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827;
    classDef process fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#111827;
    classDef store fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#111827;
    class Member,Deliverer actor;
    class System process;
    class Store store;
""",
    "dfd_level0.mmd": """%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#dbeafe", "primaryBorderColor": "#1d4ed8", "lineColor": "#0f172a", "fontFamily": "Arial"}, "flowchart": {"curve": "basis", "nodeSpacing": 64, "rankSpacing": 92}}}%%
flowchart LR
    Member[Thanh vien]
    Courier[Nguoi giao sach]
    D1[(D1 Member)]
    D2[(D2 Book)]
    D3[(D3 ExchangeTransaction)]
    D4[(D4 Message)]
    D5[(D5 ActivityTracking)]

    P1((1.0 Quan ly tai khoan va ho so))
    P2((2.0 Quan ly danh muc sach))
    P3((3.0 Quan ly chatbox va ung tuyen))
    P4((4.0 Xac nhan giao nhan va cap nhat diem))
    P5((5.0 Theo doi hoat dong va thong bao))

    Member --> P1
    P1 --> Member
    P1 <-->|du lieu thanh vien| D1

    Member --> P2
    P2 --> Member
    P2 <-->|book CRUD| D2
    P2 <-->|mo transaction| D3

    Member --> P3
    Courier --> P3
    P3 <-->|member/role| D1
    P3 <-->|participant state| D3
    P3 <-->|message/notification| D4
    P3 --> Member
    P3 --> Courier

    Member --> P4
    Courier --> P4
    P4 <-->|points| D1
    P4 <-->|available| D2
    P4 <-->|locked/archive| D3
    P4 <-->|confirm messages| D4

    P5 <-->|message stream| D4
    P5 <-->|last read| D5
    P5 --> Member
    P5 --> Courier

    classDef actor fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827;
    classDef process fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#111827;
    classDef store fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#111827;
    class Member,Courier actor;
    class P1,P2,P3,P4,P5 process;
    class D1,D2,D3,D4,D5 store;
""",
    "dfd_account_profile.mmd": """%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#dbeafe", "primaryBorderColor": "#1d4ed8", "lineColor": "#0f172a", "fontFamily": "Arial"}, "flowchart": {"curve": "basis", "nodeSpacing": 70, "rankSpacing": 85}}}%%
flowchart LR
    User[Thanh vien]
    P11((1.1 Dang ky))
    P12((1.2 Dang nhap))
    P13((1.3 Xac thuc token))
    P14((1.4 Cap nhat ho so/avatar))
    D1[(Member)]
    DAvatar[(avatar/)]

    User --> P11
    P11 --> User
    User --> P12
    P12 --> User
    User --> P13
    User --> P14
    P11 -->|insert member + 20 diem| D1
    P12 <-->|verify password_hash| D1
    P13 <-->|load member| D1
    P14 <-->|update profile| D1
    P14 -->|save avatar file| DAvatar

    classDef actor fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827;
    classDef process fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#111827;
    classDef store fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#111827;
    class User actor;
    class P11,P12,P13,P14 process;
    class D1,DAvatar store;
""",
    "dfd_book_catalog.mmd": """%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#dbeafe", "primaryBorderColor": "#1d4ed8", "lineColor": "#0f172a", "fontFamily": "Arial"}, "flowchart": {"curve": "basis", "nodeSpacing": 78, "rankSpacing": 100}}}%%
flowchart LR
    Owner[Chu sach]
    Member[Thanh vien]
    P21((2.1 Tao sach))
    P22((2.2 Sua sach))
    P23((2.3 Xoa sach))
    P24((2.4 Liet ke/tim loc sach))
    P25((2.5 Gia han sach cho muon))
    D2[(Book)]
    D3[(ExchangeTransaction)]
    D4[(Message)]
    Pic[(pic/)]

    Owner --> P21
    Owner --> P22
    Owner --> P23
    Owner --> P25
    Member --> P24
    P24 --> Member

    P21 --> D2
    P21 --> Pic
    P21 --> D3
    P21 --> D4
    P22 <--> D2
    P23 <--> D2
    P23 --> D3
    P23 --> D4
    P24 <-->|read/filter| D2
    P25 <--> D2
    P25 --> D3
    P25 --> D4

    classDef actor fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827;
    classDef process fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#111827;
    classDef store fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#111827;
    class Owner,Member actor;
    class P21,P22,P23,P24,P25 process;
    class D2,D3,D4,Pic store;
""",
    "dfd_transaction_chatbox.mmd": """%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#dbeafe", "primaryBorderColor": "#1d4ed8", "lineColor": "#0f172a", "fontFamily": "Arial"}, "flowchart": {"curve": "basis", "nodeSpacing": 78, "rankSpacing": 100}}}%%
flowchart LR
    Applicant[Requester/Courier]
    Owner[Owner]
    P31((3.1 Mo chatbox))
    P32((3.2 Ung tuyen vai tro))
    P33((3.3 Thong ke ung tuyen))
    P34((3.4 Owner chap nhan))
    P35((3.5 Chat va thong bao))
    P36((3.6 Roi/xoa nguoi tham gia))
    D1[(Member)]
    D2[(Book)]
    D3[(ExchangeTransaction)]
    D4[(Message)]

    Owner --> P31
    P31 <--> D2
    P31 <--> D3
    P31 --> D4
    Applicant --> P32
    Applicant --> P33
    Owner --> P33
    Owner --> P34
    Applicant --> P35
    Owner --> P35
    Applicant --> P36
    Owner --> P36

    P32 <--> D1
    P32 <--> D3
    P32 --> D4
    P33 <--> D3
    P33 <--> D4
    P34 <--> D3
    P34 --> D4
    P35 <--> D4
    P36 <--> D3
    P36 --> D4

    classDef actor fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827;
    classDef process fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#111827;
    classDef store fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#111827;
    class Applicant,Owner actor;
    class P31,P32,P33,P34,P35,P36 process;
    class D1,D2,D3,D4 store;
""",
    "dfd_confirmation_points.mmd": """%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#dbeafe", "primaryBorderColor": "#1d4ed8", "lineColor": "#0f172a", "fontFamily": "Arial"}, "flowchart": {"curve": "basis", "nodeSpacing": 78, "rankSpacing": 100}}}%%
flowchart LR
    Participants[Owner / Requester / Courier]
    P41((4.1 Tao yeu cau xac nhan))
    P42((4.2 Duyet thong bao xac nhan))
    P43((4.3 Khoa chatbox))
    P44((4.4 Ap dung diem))
    P45((4.5 Archive giao dich va khoa sach))
    D1[(Member.points)]
    D2[(Book.available)]
    D3[(ExchangeTransaction)]
    D4[(Message)]

    Participants --> P41
    Participants --> P42
    P41 --> D4
    P42 <--> D4
    P42 --> P43
    P43 <--> D3
    P43 -->|enough confirmations| P44
    P44 <-->|+/- points| D1
    P44 <--> D3
    P44 --> P45
    P45 <--> D2
    P45 <--> D3

    classDef actor fill:#ffffff,stroke:#111827,stroke-width:2px,color:#111827;
    classDef process fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#111827;
    classDef store fill:#fef3c7,stroke:#92400e,stroke-width:2px,color:#111827;
    class Participants actor;
    class P41,P42,P43,P44,P45 process;
    class D1,D2,D3,D4 store;
""",
    "erd.mmd": """%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2ff", "primaryBorderColor": "#1e40af", "lineColor": "#0f172a", "fontFamily": "Arial"}}}%%
erDiagram
    MEMBER ||--o{ BOOK : owns
    MEMBER ||--o{ EXCHANGE_TRANSACTION : owner
    MEMBER ||--o{ EXCHANGE_TRANSACTION : requester
    MEMBER ||--o{ EXCHANGE_TRANSACTION : courier
    BOOK ||--o{ EXCHANGE_TRANSACTION : has
    EXCHANGE_TRANSACTION ||--o{ MESSAGE : contains
    MEMBER ||--o{ MESSAGE : sends
    MEMBER ||--o{ MESSAGE : approves
    MEMBER ||--o{ ACTIVITY_TRACKING : tracks
    EXCHANGE_TRANSACTION ||--o{ ACTIVITY_TRACKING : scopes

    MEMBER {
      int id PK
      string name
      string email
      string password_hash
      int points
      string gender
      int age
      string avatar_path
      string biography
    }
    BOOK {
      int id PK
      int owner_id FK
      string title
      string genre
      string author
      string description
      int publication_year
      string condition
      string exchange_mode
      bool available
      string picture_path
    }
    EXCHANGE_TRANSACTION {
      int id PK
      int book_id FK
      int owner_id FK
      string exchange_mode
      int requester_id FK
      int courier_id FK
      bool owner_confirmed
      bool requester_confirmed
      bool locked
      bool points_applied
      bool archived
    }
    MESSAGE {
      int message_id PK
      int user_id FK
      int transaction_id FK
      string message
      string applied_role
      string notification_type
      int approver_id FK
      string approver_role
      bool accepted
      datetime timestamp
    }
    ACTIVITY_TRACKING {
      int id PK
      int member_id FK
      int transaction_id FK
      string tab
      datetime last_timestamp
    }
""",
}

DIAGRAM_LAYOUTS = {
    "use_case_overview.mmd": {
        "width": 1320,
        "height": 780,
        "nodes": [
            ("owner", "Owner\n(chủ sách)", 1100, 185, 155, 75, "actor"),
            ("requester", "Requester\n(người nhận/mượn)", 45, 325, 165, 85, "actor"),
            ("courier", "Courier\n(người giao sách)", 45, 565, 165, 85, "actor"),
            ("system", "Book Exchange Club", 250, 55, 800, 670, "system"),
            ("uc1", "Tài khoản\n& hồ sơ", 330, 105, 175, 78, "usecase"),
            ("uc2", "Tìm kiếm /\nlọc sách", 580, 105, 180, 78, "usecase"),
            ("uc3", "Đăng / sửa /\nxóa sách", 325, 250, 180, 82, "usecase"),
            ("uc4", "Chấp nhận\nrequester/courier", 575, 238, 190, 95, "usecase"),
            ("uc5", "Xóa người\ntham gia", 815, 250, 170, 82, "usecase"),
            ("uc6", "Renew sách\nloan archived", 815, 375, 170, 82, "usecase"),
            ("uc7", "Ứng tuyển\nrequester", 325, 430, 175, 78, "usecase"),
            ("uc8", "Rút đơn\nứng tuyển", 570, 430, 175, 78, "usecase"),
            ("uc9", "Chatbox và\nthông báo", 805, 430, 180, 85, "usecase"),
            ("uc10", "Xác nhận\ngiao nhận", 805, 565, 175, 85, "usecase"),
            ("uc11", "Ứng tuyển\ngiao sách", 335, 595, 185, 78, "usecase"),
            ("uc12", "Nhận và\ngiao sách", 570, 595, 175, 78, "usecase"),
        ],
        "edges": [
            ("owner", "uc1", ""), ("owner", "uc2", ""), ("owner", "uc3", ""), ("owner", "uc4", ""),
            ("owner", "uc5", ""), ("owner", "uc6", ""), ("owner", "uc9", ""), ("owner", "uc10", ""),
            ("requester", "uc1", ""), ("requester", "uc2", ""), ("requester", "uc7", ""), ("requester", "uc8", ""),
            ("requester", "uc9", ""), ("requester", "uc10", ""),
            ("courier", "uc1", ""), ("courier", "uc9", ""), ("courier", "uc10", ""),
            ("courier", "uc11", ""), ("courier", "uc12", ""),
        ],
    },
    "architecture.mmd": {
        "width": 1180,
        "height": 470,
        "nodes": [
            ("browser", "Trình duyệt\nngười dùng", 50, 180, 150, 80, "actor"),
            ("storage", "localStorage\nhttt_token\nhttt_member", 50, 330, 160, 90, "store"),
            ("frontend", "SvelteKit 5 Frontend\nTypeScript + Vite\nroutes + components", 305, 145, 245, 150, "process"),
            ("api", "FastAPI Backend\nbackend/main.py\nREST API + CORS", 660, 145, 245, 150, "process"),
            ("sqlite", "SQLite\n db.sqlite3", 970, 75, 150, 80, "store"),
            ("pic", "pic/\nảnh sách", 970, 210, 150, 75, "store"),
            ("avatar", "avatar/\nảnh đại diện", 970, 335, 150, 75, "store"),
        ],
        "edges": [
            ("browser", "frontend", "UI"),
            ("browser", "storage", "token/session"),
            ("frontend", "api", "REST API"),
            ("api", "sqlite", "SQLModel"),
            ("api", "pic", "StaticFiles /pic"),
            ("api", "avatar", "StaticFiles /avatar"),
        ],
    },
    "dfd_context.mmd": {
        "width": 1260,
        "height": 620,
        "nodes": [
            ("member", "Thành viên\ncâu lạc bộ", 55, 125, 180, 90, "actor"),
            ("courier", "Người giao sách\nmiễn phí", 55, 405, 180, 90, "actor"),
            ("system", "Hệ thống\nBook Exchange Club", 500, 245, 260, 135, "process"),
            ("store", "Dữ liệu hệ thống\nMember, Book,\nTransaction, Message", 945, 245, 250, 135, "store"),
        ],
        "edges": [
            ("member", "system", "tài khoản, sách,\nứng tuyển, chat", -30, -28),
            ("system", "member", "catalog, trạng thái,\nthông báo, điểm", -35, 30),
            ("courier", "system", "ứng tuyển giao,\nxác nhận", -32, -28),
            ("system", "courier", "nhiệm vụ giao,\nđiểm thưởng", -36, 30),
            ("system", "store", "đọc/ghi\ntrạng thái", 0, -20),
        ],
    },
    "dfd_level0.mmd": {
        "width": 1420,
        "height": 930,
        "nodes": [
            ("member", "Thành viên", 40, 255, 150, 75, "actor"),
            ("courier", "Courier", 40, 650, 150, 75, "actor"),
            ("p1", "1.0\nTài khoản\n& hồ sơ", 285, 70, 160, 110, "process"),
            ("p2", "2.0\nDanh mục\nsách", 285, 275, 160, 110, "process"),
            ("p3", "3.0\nChatbox\n& ứng tuyển", 560, 260, 175, 120, "process"),
            ("p4", "4.0\nXác nhận\n& điểm", 840, 430, 170, 120, "process"),
            ("p5", "5.0\nActivity\n& unread", 560, 660, 175, 110, "process"),
            ("d1", "D1 Member", 1170, 80, 180, 60, "store"),
            ("d2", "D2 Book", 1170, 250, 180, 60, "store"),
            ("d3", "D3 Transaction", 1170, 420, 180, 60, "store"),
            ("d4", "D4 Message", 1170, 610, 180, 60, "store"),
            ("d5", "D5 Activity", 1170, 770, 180, 60, "store"),
        ],
        "edges": [
            ("member", "p1", ""),
            ("p1", "member", ""),
            ("member", "p2", ""),
            ("p2", "member", ""),
            ("member", "p3", ""),
            ("courier", "p3", ""),
            ("p3", "member", ""),
            ("p3", "courier", ""),
            ("member", "p4", ""),
            ("courier", "p4", ""),
            ("p1", "d1", "member data", 0, -20),
            ("p2", "d2", "book data", 0, -22),
            ("p2", "d3", "listing tx", 0, 30),
            ("p3", "d1", "role/member", 0, -30),
            ("p3", "d3", "participants", 0, -22),
            ("p3", "d4", "messages", 0, 38),
            ("p4", "d1", "points", 0, -36),
            ("p4", "d2", "available", 0, -28),
            ("p4", "d3", "locked/archive", 8, -6),
            ("p4", "d4", "confirm", 0, 28),
            ("p5", "d4", "message stream", 0, -24),
            ("p5", "d5", "last read", 0, 22),
            ("p5", "member", ""),
            ("p5", "courier", ""),
        ],
    },
    "dfd_account_profile.mmd": {
        "width": 1320,
        "height": 650,
        "nodes": [
            ("user", "Thành viên", 45, 290, 155, 80, "actor"),
            ("p11", "1.1\nĐăng ký", 300, 85, 155, 95, "process"),
            ("p12", "1.2\nĐăng nhập", 300, 285, 155, 95, "process"),
            ("p14", "1.4\nCập nhật hồ sơ\nvà avatar", 300, 465, 180, 105, "process"),
            ("p13", "1.3\nXác thực token", 620, 35, 175, 95, "process"),
            ("d1", "D1 Member\npassword_hash\npoints=20", 975, 160, 220, 100, "store"),
            ("avatar", "avatar/\nfile ảnh", 995, 465, 185, 85, "store"),
        ],
        "edges": [
            ("user", "p11", ""),
            ("p11", "user", ""),
            ("user", "p12", ""),
            ("p12", "user", ""),
            ("user", "p13", ""),
            ("user", "p14", ""),
            ("p11", "d1", "insert member\n+20 điểm", 0, -18),
            ("p12", "d1", "verify\npassword_hash", 0, 24),
            ("p13", "d1", "load member", 0, -20),
            ("p14", "d1", "update profile", 0, -28),
            ("p14", "avatar", "save file", 0, 18),
        ],
    },
    "dfd_book_catalog.mmd": {
        "width": 1500,
        "height": 900,
        "nodes": [
            ("owner", "Owner", 45, 245, 145, 75, "actor"),
            ("member", "Thành viên", 45, 690, 145, 75, "actor"),
            ("p21", "2.1\nTạo sách", 305, 80, 155, 95, "process"),
            ("p22", "2.2\nSửa sách", 305, 250, 155, 95, "process"),
            ("p23", "2.3\nXóa sách", 305, 425, 155, 95, "process"),
            ("p25", "2.5\nRenew loan", 610, 105, 165, 95, "process"),
            ("p24", "2.4\nLiệt kê,\ntìm kiếm, lọc", 610, 665, 185, 110, "process"),
            ("d2", "D2 Book", 1180, 95, 185, 60, "store"),
            ("pic", "pic/\nảnh sách", 1185, 250, 175, 75, "store"),
            ("d3", "D3 Transaction", 1180, 430, 195, 60, "store"),
            ("d4", "D4 Message", 1180, 620, 185, 60, "store"),
        ],
        "edges": [
            ("owner", "p21", ""),
            ("owner", "p22", ""),
            ("owner", "p23", ""),
            ("owner", "p25", "loan archived", -42, -24),
            ("member", "p24", "GET /api/books", -20, -22),
            ("p24", "member", ""),
            ("p21", "d2", ""),
            ("p21", "pic", ""),
            ("p21", "d3", ""),
            ("p21", "d4", "", 0, 0),
            ("p22", "d2", ""),
            ("p23", "d2", ""),
            ("p23", "d3", ""),
            ("p23", "d4", ""),
            ("p24", "d2", ""),
            ("p25", "d2", ""),
            ("p25", "d3", ""),
            ("p25", "d4", ""),
        ],
    },
    "dfd_transaction_chatbox.mmd": {
        "width": 1500,
        "height": 850,
        "nodes": [
            ("owner", "Owner", 45, 170, 150, 75, "actor"),
            ("applicant", "Requester /\nCourier", 45, 445, 160, 85, "actor"),
            ("p31", "3.1\nMở chatbox", 305, 75, 155, 95, "process"),
            ("p32", "3.2\nỨng tuyển\nvai trò", 305, 290, 160, 105, "process"),
            ("p33", "3.3\nThống kê\nứng tuyển", 305, 535, 160, 105, "process"),
            ("p34", "3.4\nOwner\nchấp nhận", 640, 135, 165, 105, "process"),
            ("p35", "3.5\nChat và\nnotification", 640, 390, 180, 110, "process"),
            ("p36", "3.6\nRời / xóa\nparticipant", 640, 630, 180, 105, "process"),
            ("d1", "D1 Member", 1190, 80, 175, 60, "store"),
            ("d2", "D2 Book", 1190, 220, 175, 60, "store"),
            ("d3", "D3 Transaction", 1190, 365, 200, 60, "store"),
            ("d4", "D4 Message", 1190, 590, 180, 60, "store"),
        ],
        "edges": [
            ("owner", "p31", ""),
            ("owner", "p33", ""),
            ("owner", "p34", ""),
            ("owner", "p35", ""),
            ("owner", "p36", ""),
            ("applicant", "p32", ""),
            ("applicant", "p33", ""),
            ("applicant", "p35", ""),
            ("applicant", "p36", ""),
            ("p31", "d2", ""),
            ("p31", "d3", ""),
            ("p31", "d4", ""),
            ("p32", "d1", ""),
            ("p32", "d3", ""),
            ("p32", "d4", ""),
            ("p33", "d3", ""),
            ("p33", "d4", ""),
            ("p34", "d3", ""),
            ("p34", "d4", ""),
            ("p35", "d4", ""),
            ("p36", "d3", ""),
            ("p36", "d4", ""),
        ],
    },
    "dfd_confirmation_points.mmd": {
        "width": 1420,
        "height": 760,
        "nodes": [
            ("participants", "Owner /\nRequester /\nCourier", 55, 300, 175, 115, "actor"),
            ("p41", "4.1\nTạo yêu cầu\nxác nhận", 320, 155, 170, 105, "process"),
            ("p42", "4.2\nDuyệt thông báo\nxác nhận", 320, 390, 175, 110, "process"),
            ("d4", "D4 Message", 590, 280, 175, 65, "store"),
            ("p43", "4.3\nKhóa chatbox", 815, 135, 160, 95, "process"),
            ("p44", "4.4\nÁp dụng điểm", 815, 345, 165, 100, "process"),
            ("p45", "4.5\nArchive\nvà khóa sách", 815, 565, 175, 105, "process"),
            ("d1", "D1 Member.points", 1145, 180, 205, 60, "store"),
            ("d2", "D2 Book.available", 1145, 390, 205, 60, "store"),
            ("d3", "D3 Transaction", 1145, 590, 205, 60, "store"),
        ],
        "edges": [
            ("participants", "p41", "request confirm", -18, -22),
            ("participants", "p42", "approve", -18, 24),
            ("p41", "d4", ""),
            ("p42", "d4", ""),
            ("p42", "p43", ""),
            ("p43", "p44", "đủ xác nhận", 0, -20),
            ("p43", "d3", ""),
            ("p44", "d1", "+/- điểm", 0, -24),
            ("p44", "d3", ""),
            ("p44", "p45", ""),
            ("p45", "d2", ""),
            ("p45", "d3", "archived", 0, 22),
        ],
    },
    "erd.mmd": {
        "width": 1360,
        "height": 940,
        "nodes": [
            ("member", "MEMBER\nid PK\nname\nemail\npassword_hash\npoints\ngender\nage\navatar_path\nbiography", 60, 70, 265, 285, "entity"),
            ("book", "BOOK\nid PK\nowner_id FK\ntitle\ngenre\nauthor\ndescription\npublication_year\ncondition\nexchange_mode\navailable\npicture_path", 60, 510, 300, 345, "entity"),
            ("txn", "EXCHANGE_TRANSACTION\nid PK\nbook_id FK\nowner_id FK\nexchange_mode\nrequester_id FK\ncourier_id FK\nowner_confirmed\nrequester_confirmed\nlocked\npoints_applied\narchived", 520, 280, 350, 370, "entity"),
            ("msg", "MESSAGE\nmessage_id PK\nuser_id FK\ntransaction_id FK\nmessage\napplied_role\nnotification_type\napprover_id FK\napprover_role\naccepted\ntimestamp", 980, 70, 310, 320, "entity"),
            ("activity", "ACTIVITY_TRACKING\nid PK\nmember_id FK\ntransaction_id FK\ntab\nlast_timestamp", 430, 710, 320, 205, "entity"),
        ],
        "edges": [
            ("member", "book", "owns", -48, 0),
            ("book", "txn", "has", -18, 22),
            ("member", "txn", "owner/requester/courier", -8, -48),
            ("txn", "msg", "contains", 34, -22),
            ("member", "msg", "sends/approves", 0, -36),
            ("member", "activity", "tracks", 20, -90),
            ("txn", "activity", "scopes", 38, 22),
        ],
    },
}


def diagram_block(file_name: str, caption: str) -> str:
    image_name = file_name.replace(".mmd", f".{REPORT_IMAGE_EXTENSION}")
    return (
        f"{caption}\n\n"
        f"![{caption}](report_assets/diagrams/rendered/{image_name})\n\n"
        f"Nguon so do: `docs/report_assets/diagrams/src/{file_name}`\n\n"
    )


def svg_escape(text: str) -> str:
    return html.escape(text, quote=True)


def text_lines(label: str) -> list[str]:
    return label.split("\n")


def node_center(node: tuple) -> tuple[float, float]:
    _, _, x, y, w, h, _ = node
    return x + w / 2, y + h / 2


def endpoint(source: tuple, target: tuple) -> tuple[float, float]:
    _, _, sx, sy, sw, sh, sshape = source
    scx, scy = node_center(source)
    tcx, tcy = node_center(target)
    dx = tcx - scx
    dy = tcy - scy
    if dx == 0 and dy == 0:
        return scx, scy
    if sshape in {"process", "usecase"}:
        rx = sw / 2
        ry = sh / 2
        scale = 1 / max(((dx / rx) ** 2 + (dy / ry) ** 2) ** 0.5, 0.01)
        return scx + dx * scale, scy + dy * scale
    scale = min((sw / 2) / max(abs(dx), 0.01), (sh / 2) / max(abs(dy), 0.01))
    return scx + dx * scale, scy + dy * scale


def node_svg(node: tuple) -> str:
    node_id, label, x, y, w, h, shape = node
    lines = text_lines(label)
    fill = {
        "actor": "#ffffff",
        "system": "#f8fafc",
        "process": "#dbeafe",
        "usecase": "#ffffff",
        "store": "#fef3c7",
        "entity": "#eef2ff",
    }.get(shape, "#ffffff")
    stroke = "#111827" if shape != "entity" else "#1e40af"
    if shape in {"process", "usecase"}:
        body = f'<ellipse cx="{x + w / 2}" cy="{y + h / 2}" rx="{w / 2}" ry="{h / 2}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    else:
        radius = 14 if shape in {"actor", "system", "store", "entity"} else 8
        body = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        if shape == "entity":
            body += f'<line x1="{x + 12}" y1="{y + 42}" x2="{x + w - 12}" y2="{y + 42}" stroke="{stroke}" stroke-width="1.5"/>'
    if shape == "entity":
        title = lines[0]
        attrs = lines[1:]
        text = [
            f'<text x="{x + w / 2}" y="{y + 29}" text-anchor="middle" '
            f'font-size="15" font-weight="700" font-family="Arial, sans-serif" fill="#111827">{svg_escape(title)}</text>'
        ]
        line_height = 17
        for index, line in enumerate(attrs):
            text.append(
                f'<text x="{x + 20}" y="{y + 64 + index * line_height}" text-anchor="start" '
                f'font-size="13.5" font-family="Arial, sans-serif" fill="#0f172a">{svg_escape(line)}</text>'
            )
        return f'<g id="{svg_escape(node_id)}">{body}{"".join(text)}</g>'
    font_size = 15 if shape == "entity" else 16
    weight = "700" if shape in {"actor", "system", "entity"} else "600"
    total = len(lines)
    line_height = 20 if shape != "entity" else 18
    start_y = y + h / 2 - (total - 1) * line_height / 2 + font_size / 3
    text = []
    for index, line in enumerate(lines):
        text.append(
            f'<text x="{x + w / 2}" y="{start_y + index * line_height}" text-anchor="middle" '
            f'font-size="{font_size}" font-weight="{weight if index == 0 else 400}" '
            f'font-family="Arial, sans-serif" fill="#111827">{svg_escape(line)}</text>'
        )
    return f'<g id="{svg_escape(node_id)}">{body}{"".join(text)}</g>'


def edge_svg(source: tuple, target: tuple, label: str, label_dx: float = 0, label_dy: float = 0) -> str:
    sx, sy = endpoint(source, target)
    tx, ty = endpoint(target, source)
    mid_x = (sx + tx) / 2 + label_dx
    mid_y = (sy + ty) / 2 + label_dy
    path = f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="#0f172a" stroke-width="1.9" marker-end="url(#arrow)"/>'
    if not label:
        return path
    lines = text_lines(label)
    label_width = max(48, max(len(line) for line in lines) * 7 + 14)
    label_height = len(lines) * 16 + 8
    rect = (
        f'<rect x="{mid_x - label_width / 2:.1f}" y="{mid_y - label_height / 2 - 5:.1f}" '
        f'width="{label_width}" height="{label_height}" rx="4" fill="#ffffff" stroke="#cbd5e1" stroke-width="1"/>'
    )
    text = []
    for index, line in enumerate(lines):
        text.append(
            f'<text x="{mid_x}" y="{mid_y - 4 + index * 16}" text-anchor="middle" '
            f'font-size="13" font-family="Arial, sans-serif" fill="#1f2937">{svg_escape(line)}</text>'
        )
    return path + rect + "".join(text)


def render_svg(file_name: str, layout: dict) -> str:
    width = layout["width"]
    height = layout["height"]
    nodes = {node[0]: node for node in layout["nodes"]}
    edge_markup = []
    for edge in layout["edges"]:
        source_id, target_id, label, *label_offset = edge
        label_dx = label_offset[0] if len(label_offset) > 0 else 0
        label_dy = label_offset[1] if len(label_offset) > 1 else 0
        edge_markup.append(edge_svg(nodes[source_id], nodes[target_id], label, label_dx, label_dy))
    background_node_markup = [node_svg(node) for node in layout["nodes"] if node[6] == "system"]
    foreground_node_markup = [node_svg(node) for node in layout["nodes"] if node[6] != "system"]
    title = diagram_title(file_name)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth">
      <path d="M2,2 L10,6 L2,10 Z" fill="#111827"/>
    </marker>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#9ca3af" flood-opacity="0.25"/>
    </filter>
  </defs>
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{width / 2}" y="30" text-anchor="middle" font-size="20" font-weight="700" font-family="Arial, sans-serif" fill="#111827">{svg_escape(title)}</text>
  <g filter="url(#shadow)">
    {''.join(background_node_markup)}
  </g>
  <g>
    {''.join(edge_markup)}
  </g>
  <g filter="url(#shadow)">
    {''.join(foreground_node_markup)}
  </g>
</svg>
"""


def render_diagram_images() -> None:
    DIAGRAM_RENDERED_DIR.mkdir(parents=True, exist_ok=True)
    for file_name, layout in DIAGRAM_LAYOUTS.items():
        svg = render_svg(file_name, layout)
        (DIAGRAM_RENDERED_DIR / file_name.replace(".mmd", ".svg")).write_text(svg, encoding="utf-8")


def diagram_title(file_name: str) -> str:
    titles = {
        "use_case_overview.mmd": "Use Case Overview",
        "architecture.mmd": "Architecture",
        "dfd_context.mmd": "DFD Context",
        "dfd_level0.mmd": "DFD Level 0",
        "dfd_account_profile.mmd": "DFD Account & Profile",
        "dfd_book_catalog.mmd": "DFD Book Catalog",
        "dfd_transaction_chatbox.mmd": "DFD Transaction & Chatbox",
        "dfd_confirmation_points.mmd": "DFD Confirmation & Points",
        "erd.mmd": "ERD",
    }
    return titles.get(file_name, file_name.replace(".mmd", "").replace("_", " ").title())


def diagram_layout_payload() -> dict:
    return {
        file_name: {**layout, "title": diagram_title(file_name)}
        for file_name, layout in DIAGRAM_LAYOUTS.items()
    }


def render_png_diagram_images() -> bool:
    if not PNG_RENDERER.exists():
        return False
    layout_json = DIAGRAM_RENDERED_DIR / "diagram_layouts.json"
    layout_json.write_text(json.dumps(diagram_layout_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    result = subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PNG_RENDERER),
            "-LayoutJson",
            str(layout_json),
            "-OutputDir",
            str(DIAGRAM_RENDERED_DIR),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and all(
        (DIAGRAM_RENDERED_DIR / file_name.replace(".mmd", ".png")).exists()
        for file_name in DIAGRAM_LAYOUTS
    )


REPORT_TEMPLATE = r"""ĐẠI HỌC QUỐC GIA HÀ NỘI
TRƯỜNG ĐẠI HỌC CÔNG NGHỆ

# TÀI LIỆU PHÂN TÍCH THIẾT KẾ HỆ THỐNG

## ĐỀ TÀI

XÂY DỰNG ỨNG DỤNG KẾT NỐI THÀNH VIÊN CÂU LẠC BỘ SÁCH ĐỂ TRAO ĐỔI VÀ CHO MƯỢN SÁCH

Backend: FastAPI + SQLModel + SQLite, triển khai trong `backend/main.py`.

Frontend: SvelteKit 5 + TypeScript + Vite, triển khai trong thư mục `frontend`.

Phiên bản tài liệu: {date}

<!-- PAGEBREAK -->

# THÔNG TIN NHÓM THỰC HIỆN

Bảng 0.1. Bảng thông tin thực hiện báo cáo

| Họ và tên | Vai trò | Nhiệm vụ |
| --- | --- | --- |
| Nhóm phát triển HTTT | Business Analyst / System Design Writer | Phân tích nghiệp vụ, đặc tả yêu cầu, mô hình hóa hệ thống, lập báo cáo thiết kế hệ thống |
| Backend | FastAPI Developer | Xây dựng API, mô hình dữ liệu, nghiệp vụ điểm, xác nhận giao dịch trong `backend/main.py` |
| Frontend | Svelte Developer | Xây dựng giao diện SvelteKit, luồng đăng nhập, quản lý sách, chatbox, thông báo và hồ sơ |

# MỤC LỤC

1. Chương 1. Tổng quan đề tài
2. Chương 2. Đặc tả yêu cầu hệ thống
3. Chương 3. Thiết kế kiến trúc tổng thể
4. Chương 4. Thiết kế kỹ thuật chi tiết
5. Chương 5. Thiết kế giao diện người dùng - UI/UX
6. Chương 6. Kế hoạch kiểm thử và triển khai
7. Chương 7. Kết luận và hướng phát triển
8. Tài liệu tham khảo

# DANH MỤC TỪ VIẾT TẮT

Bảng 0.2. Bảng danh mục từ viết tắt

| Từ viết tắt | Giải thích |
| --- | --- |
| API | Application Programming Interface - giao diện lập trình ứng dụng |
| BA | Business Analyst - chuyên viên phân tích nghiệp vụ |
| CORS | Cross-Origin Resource Sharing - cơ chế cho phép frontend gọi backend khác origin |
| CRUD | Create, Read, Update, Delete - nhóm thao tác dữ liệu cơ bản |
| DFD | Data Flow Diagram - sơ đồ luồng dữ liệu |
| ERD | Entity Relationship Diagram - sơ đồ thực thể liên kết |
| JWT | JSON Web Token - chuỗi token xác thực được ký |
| MVP | Minimum Viable Product - phiên bản khả dụng tối thiểu |
| REST | Representational State Transfer - phong cách thiết kế API HTTP |
| SQLModel | Thư viện Python kết hợp SQLAlchemy và Pydantic để khai báo model dữ liệu |
| SQLite | Hệ quản trị cơ sở dữ liệu nhúng, lưu trong file `db.sqlite3` |
| UI/UX | User Interface / User Experience - giao diện và trải nghiệm người dùng |

# DANH MỤC HÌNH ẢNH

Hình 2.1. Sơ đồ Use Case tổng quát của hệ thống

Hình 3.1. Sơ đồ kiến trúc tổng thể của hệ thống

Hình 3.2. Sơ đồ DFD mức ngữ cảnh

Hình 3.3. Sơ đồ DFD mức 0

Hình 3.4. Phân rã Tiến trình 1.0 - Quản lý tài khoản và hồ sơ

Hình 3.5. Phân rã Tiến trình 2.0 - Quản lý danh mục sách

Hình 3.6. Phân rã Tiến trình 3.0 - Quản lý chatbox và ứng tuyển vai trò

Hình 3.7. Phân rã Tiến trình 4.0 - Xác nhận giao nhận và cập nhật điểm

Hình 4.1. Sơ đồ ERD của hệ thống

# DANH MỤC BẢNG BIỂU

Bảng 1.1. Bảng công nghệ sử dụng

Bảng 2.1. Bảng quy định nghiệp vụ cốt lõi

Bảng 2.2. Bảng yêu cầu chức năng

Bảng 2.3. Bảng yêu cầu phi chức năng

Bảng 2.4 - 2.15. Các bảng đặc tả use case chính

Bảng 4.1 - 4.5. Các bảng đặc tả dữ liệu

Bảng 4.6. Bảng đặc tả API

Bảng 5.1. Bảng danh sách màn hình chính

Bảng 5.2. Bảng đặc tả kiểm soát giao diện

Bảng 6.1. Bảng kịch bản kiểm thử

Bảng 6.2. Bảng môi trường triển khai

<!-- PAGEBREAK -->

# CHƯƠNG 1. TỔNG QUAN ĐỀ TÀI

## 1.1. Giới thiệu đề tài

Đề tài hướng đến việc xây dựng một ứng dụng hỗ trợ các thành viên câu lạc bộ sách trao đổi hoặc cho mượn sách thông qua một nền tảng tập trung. Người dùng có thể đăng sách của mình, tìm kiếm sách của người khác, ứng tuyển để nhận hoặc mượn sách, tham gia chatbox theo từng giao dịch và xác nhận giao nhận để hệ thống cập nhật điểm thưởng.

Ứng dụng được triển khai theo mô hình prototype có đầy đủ luồng nghiệp vụ chính. Backend nằm trong một file duy nhất `backend/main.py`, sử dụng FastAPI để cung cấp REST API, SQLModel để khai báo bảng dữ liệu, SQLite để lưu dữ liệu cục bộ và thư mục tĩnh `pic/`, `avatar/` để lưu hình ảnh. Frontend nằm trong thư mục `frontend`, sử dụng SvelteKit 5, TypeScript, Svelte runes và Vite.

Về bản chất nghiệp vụ, hệ thống không chỉ là danh mục sách. Trọng tâm của ứng dụng là điều phối quan hệ ba vai trò trong một giao dịch: chủ sách, người nhận/mượn sách và người giao sách tự nguyện. Điểm thưởng được dùng như một cơ chế khuyến khích trao đổi: thành viên mới có 20 điểm, chủ sách nhận điểm khi trao đổi thành công, người nhận/mượn bị trừ điểm, người giao sách nhận 2 điểm khi giao hàng thành công.

## 1.2. Lý do chọn đề tài

Trong hoạt động câu lạc bộ sách, việc trao đổi sách thường diễn ra qua tin nhắn riêng, bài đăng rời rạc hoặc trao đổi trực tiếp. Cách làm này có một số hạn chế:

- Danh sách sách đang có nhu cầu trao đổi không được tập trung.
- Thành viên khó biết sách nào còn khả dụng, sách nào đã có người nhận, sách nào đang trong quá trình giao nhận.
- Việc mượn/trả hoặc trao đổi vĩnh viễn thiếu cơ chế ghi nhận trạng thái rõ ràng.
- Thành viên sẵn sàng hỗ trợ giao sách không có kênh riêng để nhận vai trò giao sách.
- Điểm thưởng nếu quản lý thủ công sẽ dễ sai lệch, đặc biệt khi cần xác nhận từ nhiều bên.

Ứng dụng giải quyết các vấn đề trên bằng cách đưa danh mục sách, chatbox giao dịch, ứng tuyển vai trò, xác nhận giao nhận và điểm thưởng vào cùng một luồng dữ liệu.

## 1.3. Mục tiêu xây dựng hệ thống

Mục tiêu tổng quát là xây dựng một ứng dụng web phục vụ trao đổi sách trong phạm vi câu lạc bộ. Các mục tiêu cụ thể gồm:

- Cho phép thành viên đăng ký tài khoản, đăng nhập và duy trì phiên làm việc bằng token.
- Cấp 20 điểm ban đầu cho mỗi thành viên mới.
- Cho phép thành viên cập nhật hồ sơ cá nhân, ảnh đại diện và thông tin giới thiệu.
- Cho phép thành viên đăng sách với tiêu đề, thể loại, tác giả, mô tả, năm xuất bản, tình trạng, hình thức trao đổi và ảnh sách.
- Hỗ trợ hai hình thức: trao đổi vĩnh viễn (`permanent`) và cho mượn (`loan`).
- Cho phép người quan tâm ứng tuyển làm requester hoặc courier trong từng chatbox giao dịch.
- Cho phép chủ sách chấp nhận, xóa hoặc thay thế requester/courier.
- Cho phép các bên đã được chấp nhận chat và nhận thông báo trong từng giao dịch.
- Cập nhật điểm sau khi quá trình giao nhận được xác nhận đầy đủ.
- Duy trì Archive như lớp ghi nhận giao dịch read-only để các thành viên liên quan có thể xem lại vai trò, trạng thái và biến động điểm sau khi hoàn tất.
- Lưu vết tin nhắn, thông báo, trạng thái đọc và trạng thái giao dịch.

## 1.4. Phạm vi hệ thống

### 1.4.1. Phạm vi chức năng

Phạm vi triển khai hiện tại bao gồm thành viên câu lạc bộ, sách, giao dịch, chatbox, thông báo, xác nhận giao nhận và điểm thưởng. Hệ thống không có vai trò quản trị riêng; quyền thao tác chủ yếu dựa trên quan hệ sở hữu sách hoặc vai trò đã được chấp nhận trong giao dịch.

Các nhóm chức năng chính:

- Quản lý tài khoản: đăng ký, đăng nhập, đọc thông tin phiên hiện tại.
- Quản lý hồ sơ: xem hồ sơ công khai, sửa hồ sơ cá nhân, upload avatar.
- Quản lý sách: tạo, sửa, xóa, xem danh sách, tìm kiếm và lọc sách.
- Quản lý chatbox: mở chatbox theo sách, ứng tuyển requester/courier, rút đơn, chấp nhận, rời hoặc xóa thành viên khỏi chatbox.
- Quản lý thông báo: tạo thông báo hệ thống trong chatbox, phê duyệt thông báo có yêu cầu xác nhận, thống kê unread.
- Quản lý xác nhận giao nhận: xác nhận trực tiếp owner-requester hoặc xác nhận hai chặng owner-courier và courier-requester.
- Quản lý điểm: kiểm tra điểm khả dụng trước khi requester ứng tuyển, áp dụng cộng/trừ điểm khi giao dịch hoàn tất.
- Lưu trữ giao dịch hoàn tất: đưa transaction đã archived vào khu vực Archive như một lớp record minh bạch giữa owner, requester và courier.
- Gia hạn sách cho mượn: chủ sách có thể tạo listing mới từ một giao dịch loan đã archived.

### 1.4.2. Giới hạn của hệ thống

Đây là một prototype tập trung vào demo nghiệp vụ, do đó có một số giới hạn:

- Chưa có phân quyền quản trị nâng cao ngoài quyền chủ sở hữu sách và vai trò trong giao dịch.
- Chưa có xác thực OAuth hoặc xác minh email.
- Chatbox dùng polling định kỳ 1.8 giây thay vì WebSocket realtime.
- Cơ sở dữ liệu dùng SQLite cục bộ, phù hợp prototype hơn là triển khai nhiều người dùng quy mô lớn.
- Token JWT dùng secret môi trường `JWT_SECRET`, nhưng mặc định vẫn có fallback local.
- Chưa có cơ chế trả sách riêng cho giao dịch `loan`; trạng thái hiện tại tập trung vào hoàn tất giao nhận ban đầu và cho phép renew listing sau khi archived.
- Chưa có kiểm thử tự động đi kèm trong repository hiện tại.

## 1.5. Công nghệ sử dụng

Bảng 1.1. Bảng công nghệ sử dụng

| Thành phần | Công nghệ sử dụng | Vai trò trong hệ thống |
| --- | --- | --- |
| Backend | FastAPI | Xây dựng REST API, xử lý request/response, khai báo route trong `backend/main.py` |
| ORM / Schema | SQLModel | Khai báo model bảng và model payload theo kiểu Python type hint |
| Database | SQLite | Lưu dữ liệu thành viên, sách, giao dịch, tin nhắn và trạng thái hoạt động trong `db.sqlite3` |
| Static file | FastAPI StaticFiles | Phục vụ ảnh sách trong `/pic/*` và avatar trong `/avatar/*` |
| Authentication | JWT tự cài đặt bằng HMAC SHA-256 | Sinh/đọc bearer token, lưu token phía frontend |
| Frontend | SvelteKit 5 | Xây dựng route giao diện, trạng thái reactive và điều hướng |
| Language frontend | TypeScript | Định nghĩa type cho Member, Book, Transaction, Message và các response API |
| Build tool | Vite | Chạy dev server và build frontend |
| UI icons | `@lucide/svelte` | Icon cho button, tab, trạng thái, thông báo và thao tác |

# CHƯƠNG 2. ĐẶC TẢ YÊU CẦU HỆ THỐNG

## 2.1. Khảo sát hiện trạng

### 2.1.1. Quy trình hiện tại

Trước khi có hệ thống, một câu lạc bộ sách thường trao đổi theo quy trình thủ công:

1. Thành viên đăng thông tin sách lên nhóm chat hoặc thông báo trực tiếp.
2. Người quan tâm liên hệ riêng với chủ sách.
3. Hai bên tự thỏa thuận nhận sách, mượn sách hoặc nhờ người giao hộ.
4. Nếu có điểm thưởng, điểm được ghi nhận thủ công sau khi hai bên báo đã hoàn tất.
5. Lịch sử giao dịch, tin nhắn và trạng thái sách không được lưu tập trung.

### 2.1.2. Vấn đề tồn tại

Quy trình thủ công dẫn tới các vấn đề nghiệp vụ đáng chú ý:

- Khó kiểm soát trạng thái sách vì một sách có thể được nhiều người quan tâm cùng lúc.
- Không có dữ liệu rõ ràng để biết ai đang là requester hoặc courier của giao dịch.
- Người giao sách miễn phí khó tìm được giao dịch cần hỗ trợ.
- Chủ sách khó theo dõi nhiều yêu cầu khác nhau nếu chỉ dùng tin nhắn riêng.
- Điểm thưởng dễ bị cộng/trừ sớm nếu chưa có xác nhận giao nhận đầy đủ.
- Thành viên không có nơi xem lại lịch sử chatbox hoặc thông báo liên quan đến mình.

### 2.1.3. Nhu cầu xây dựng hệ thống mới

Hệ thống mới cần tạo ra một kênh tập trung để đăng sách, nhận yêu cầu, trao đổi trong chatbox, xác nhận giao nhận và cập nhật điểm. Mọi giao dịch phải có trạng thái rõ ràng: mở, có requester/courier, locked, points_applied và archived. Khi giao dịch đã archived, khu vực Archive đóng vai trò như lớp ghi nhận giao dịch để các bên liên quan có thể xem lại lịch sử, vai trò và biến động điểm, qua đó tăng tính minh bạch giữa các thành viên. Các thao tác nhạy cảm như chấp nhận requester/courier, xóa người tham gia hoặc cập nhật điểm phải được kiểm soát bằng role trong giao dịch.

## 2.2. Yêu cầu nghiệp vụ

### 2.2.1. Mục tiêu nghiệp vụ

Mục tiêu nghiệp vụ là giúp câu lạc bộ sách vận hành việc trao đổi sách minh bạch, có khuyến khích bằng điểm và giảm phụ thuộc vào thỏa thuận rời rạc bên ngoài hệ thống. Thành viên có thể nhìn thấy sách khả dụng, chủ sách quản lý sách của mình, requester/courier ứng tuyển theo từng giao dịch, và điểm chỉ thay đổi khi giao nhận được xác nhận đúng.

### 2.2.2. Quy trình nghiệp vụ As-is

1. Chủ sách thông báo sách trong nhóm chung.
2. Người cần sách nhắn riêng cho chủ sách.
3. Nếu cần giao hộ, hai bên tự tìm người hỗ trợ.
4. Các bên tự xác nhận bằng lời nói hoặc tin nhắn riêng.
5. Điểm nếu có được cập nhật thủ công.

### 2.2.3. Quy trình nghiệp vụ To-be

1. Thành viên đăng ký tài khoản và nhận 20 điểm.
2. Thành viên đăng sách lên hệ thống, hệ thống tạo Book và mở ExchangeTransaction tương ứng.
3. Các thành viên khác xem danh sách Available, tìm kiếm/lọc theo tên, tác giả, thể loại, năm, tình trạng, owner và exchange mode.
4. Người quan tâm vào màn hình chi tiết sách, ứng tuyển làm requester hoặc courier.
5. Chủ sách xem notification/join request và chấp nhận requester/courier phù hợp.
6. Các bên được chấp nhận trao đổi trong chatbox.
7. Khi gặp nhau, các bên tạo notification xác nhận giao nhận.
8. Hệ thống kiểm tra đúng cặp người xác nhận và đúng thứ tự giao nhận.
9. Khi đủ xác nhận, hệ thống cập nhật điểm, khóa sách, archived giao dịch, xóa các join request chưa xử lý và hiển thị bản ghi trong Archive.
10. Với sách loan đã archived, chủ sách có thể renew để tạo listing mới.

### 2.2.4. Quy định nghiệp vụ

Bảng 2.1. Bảng quy định nghiệp vụ cốt lõi

| Mã | Quy định | Diễn giải triển khai |
| --- | --- | --- |
| BR01 | Thành viên mới có 20 điểm | `register` và `create_member` tạo `Member.points = 20` |
| BR02 | Permanent exchange có giá trị 10 điểm | `points_for_mode("permanent")` trả về 10 |
| BR03 | Loan có giá trị 5 điểm | `points_for_mode("loan")` trả về 5 |
| BR04 | Requester bị trừ điểm sau khi hoàn tất | `complete_transaction_if_ready` trừ điểm requester theo exchange mode |
| BR05 | Owner được cộng điểm sau khi hoàn tất | `complete_transaction_if_ready` cộng điểm owner theo exchange mode |
| BR06 | Courier được cộng 2 điểm nếu có tham gia | `complete_transaction_if_ready` cộng 2 điểm cho courier khi `courier_id` tồn tại |
| BR07 | Requester phải đủ điểm khả dụng trước khi ứng tuyển | `ensure_requester_budget` kiểm tra điểm đã bị giữ bởi các request active/pending |
| BR08 | Owner không được tự ứng tuyển vào sách của mình | `apply_to_chatbox` chặn `member.id == transaction.owner_id` |
| BR09 | Requester và courier phải là hai người khác nhau | `apply_to_chatbox` và `accept_participant` kiểm tra xung đột vai trò |
| BR10 | Chỉ owner được chấp nhận hoặc xóa requester/courier | `accept_participant` và `kick_participant` kiểm tra `owner_id` |
| BR11 | Chatbox locked sau khi bắt đầu giao nhận vật lý | `lock_transaction` đặt `locked=True` và xóa join request |
| BR12 | Điểm chỉ áp dụng một lần | `complete_transaction_if_ready` bỏ qua nếu `points_applied=True` |
| BR13 | Giao dịch hoàn tất sẽ archived | `complete_transaction_if_ready` đặt `archived=True` |
| BR14 | Sách hoàn tất sẽ không còn available | `confirm_meeting` hoặc approval path đặt `Book.available=False` |
| BR15 | Archive là lớp record giao dịch minh bạch | Frontend lọc transaction archived liên quan đến member và hiển thị trong Archive/read-only chatbox |

## 2.3. Yêu cầu chức năng

Bảng 2.2. Bảng yêu cầu chức năng

| Mã | Tác nhân | Chức năng | Mô tả |
| --- | --- | --- | --- |
| F01 | Thành viên | Đăng ký tài khoản | Tạo tài khoản bằng name, email, password, gender, age; nhận 20 điểm và token |
| F02 | Thành viên | Đăng nhập | Xác thực email/password và nhận bearer token |
| F03 | Thành viên | Quản lý hồ sơ | Xem hồ sơ công khai, sửa hồ sơ của chính mình, upload avatar |
| F04 | Owner | Đăng sách | Tạo sách mới với thông tin bibliographic, exchange mode và ảnh sách |
| F05 | Owner | Sửa/xóa sách | Cập nhật sách của mình hoặc xóa khi chatbox chưa có participant và chưa locked/archived |
| F06 | Thành viên | Tìm kiếm và lọc sách | Lọc sách theo condition, year, exchange mode, owner và full-text search |
| F07 | Requester | Ứng tuyển nhận/mượn sách | Gửi join request với vai trò requester nếu đủ điểm khả dụng |
| F08 | Courier | Ứng tuyển giao sách | Gửi join request với vai trò courier |
| F09 | Owner | Chấp nhận participant | Chấp nhận requester/courier từ join request trong chatbox |
| F10 | Participant | Chat trong giao dịch | Gửi và xem tin nhắn nếu đã được chấp nhận vào chatbox |
| F11 | Participant | Nhận thông báo | Xem notification, join request, leave/kick, handoff confirmation |
| F12 | Participant | Xác nhận giao nhận | Tạo/approve confirmation notification theo đúng cặp owner-requester hoặc owner-courier-requester |
| F13 | Hệ thống | Cập nhật điểm | Cộng/trừ điểm sau khi đủ xác nhận |
| F14 | Owner | Gia hạn sách loan | Tạo listing mới từ loan book đã archived |
| F15 | Thành viên | Theo dõi unread | Xem số lượng message unread ở dropdown, chatbox và notification tab |
| F16 | Thành viên | Xem record giao dịch archived | Xem lại giao dịch đã hoàn tất trong Archive, gồm sách, người tham gia, trạng thái read-only và biến động điểm |

## 2.4. Yêu cầu phi chức năng

Bảng 2.3. Bảng yêu cầu phi chức năng

| Nhóm yêu cầu | Nội dung |
| --- | --- |
| Tính đúng đắn nghiệp vụ | Điểm chỉ được cập nhật sau khi giao dịch đủ xác nhận; mỗi giao dịch chỉ áp dụng điểm một lần |
| Minh bạch giao dịch | Archive giữ các transaction đã hoàn tất như record read-only để owner, requester và courier xem lại vai trò, lịch sử và điểm thay đổi |
| Dễ sử dụng | Giao diện chia rõ My books, Accepted, Applying, Available, Archive; màn hình detail có tab Book info, Chatbox, Notification |
| Phản hồi gần thời gian thực | Frontend polling mỗi 1.8 giây để cập nhật sách, giao dịch, message và unread count |
| Bảo mật cơ bản | Password được hash bằng PBKDF2-HMAC-SHA256 với salt; API hồ sơ kiểm tra bearer token khi cập nhật |
| Khả chuyển giao | Backend một file giúp đọc nhanh toàn bộ API/model/business rule trong `backend/main.py` |
| Khả mở rộng | Có thể tách router/service, thay SQLite bằng database server và thay polling bằng WebSocket ở giai đoạn sau |
| Khả dụng dữ liệu | SQLite tạo bảng khi startup; có migration nhỏ cho database prototype cũ |
| Tính nhất quán UI | Dùng component ListingSection và ConfirmModal để thống nhất list/filter/modal |

## 2.5. Sơ đồ Use Case tổng quát

{{USE_CASE_DIAGRAM}}

## 2.6. Đặc tả chi tiết các Use Case chính

### 2.6.1. Use Case Đăng ký tài khoản

Bảng 2.4. Bảng use case Đăng ký tài khoản

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Đăng ký tài khoản |
| Actor | Thành viên mới |
| Mục tiêu | Tạo tài khoản và nhận 20 điểm ban đầu |
| Tiền điều kiện | Email chưa tồn tại; password tối thiểu 4 ký tự |
| Luồng chính | Người dùng nhập name, email, password, gender, age; frontend gọi `POST /api/auth/register`; backend chuẩn hóa email/gender/age, hash password, tạo Member, trả token và member |
| Luồng thay thế | Nếu email đã tồn tại, password quá ngắn, name rỗng hoặc age/gender không hợp lệ, backend trả lỗi 400 |
| Kết quả | localStorage lưu token/member; người dùng được điều hướng tới `/books` |

### 2.6.2. Use Case Đăng nhập

Bảng 2.5. Bảng use case Đăng nhập

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Đăng nhập |
| Actor | Thành viên |
| Mục tiêu | Xác thực tài khoản để sử dụng hệ thống |
| Tiền điều kiện | Tài khoản đã được đăng ký |
| Luồng chính | Người dùng nhập email/password; frontend gọi `POST /api/auth/login`; backend kiểm tra password hash và trả bearer token |
| Luồng thay thế | Nếu email hoặc password sai, backend trả 401 |
| Kết quả | Người dùng vào màn hình `/books`; header hiển thị tên, tổng điểm và điểm khả dụng |

### 2.6.3. Use Case Cập nhật hồ sơ

Bảng 2.6. Bảng use case Cập nhật hồ sơ

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Cập nhật hồ sơ |
| Actor | Thành viên đã đăng nhập |
| Mục tiêu | Cập nhật name, gender, age, biography và avatar |
| Tiền điều kiện | Người dùng có bearer token hợp lệ và chỉ sửa hồ sơ của chính mình |
| Luồng chính | Frontend gửi FormData tới `PUT /api/members/{member_id}/profile`; backend xác thực token, kiểm tra owner profile, lưu avatar nếu có, cập nhật Member |
| Luồng thay thế | Nếu token không hợp lệ hoặc sửa hồ sơ người khác, backend trả 401/403 |
| Kết quả | Profile page và session member được refresh |

### 2.6.4. Use Case Đăng sách

Bảng 2.7. Bảng use case Đăng sách

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Đăng sách |
| Actor | Owner |
| Mục tiêu | Tạo một listing sách để trao đổi hoặc cho mượn |
| Tiền điều kiện | Người dùng đã đăng nhập; exchange mode thuộc `permanent` hoặc `loan` |
| Luồng chính | Owner nhập title, genre, author, description, publication_year, condition, exchange_mode và ảnh; frontend gọi `POST /api/books`; backend tạo Book, tạo ExchangeTransaction mở, thêm Message "Posted book" |
| Luồng thay thế | Nếu exchange_mode không hợp lệ hoặc ảnh không phải image, backend trả 400 |
| Kết quả | Sách xuất hiện trong My books của owner và Available đối với người khác nếu chưa locked/archived |

### 2.6.5. Use Case Tìm kiếm và lọc sách

Bảng 2.8. Bảng use case Tìm kiếm và lọc sách

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Tìm kiếm và lọc sách |
| Actor | Thành viên |
| Mục tiêu | Nhanh chóng tìm sách phù hợp |
| Tiền điều kiện | Người dùng đã đăng nhập và truy cập `/books` |
| Luồng chính | Frontend tải `/api/books`, `/api/transactions`, sau đó ListingSection lọc client-side theo condition, publication year, exchange mode, owner, text search |
| Luồng thay thế | Nếu backend tạm lỗi, UI giữ trạng thái hiện tại khi refresh realtime thất bại |
| Kết quả | Danh sách sách được phân nhóm My books, Accepted, Applying, Available, Archive |

### 2.6.6. Use Case Ứng tuyển requester/courier

Bảng 2.9. Bảng use case Ứng tuyển requester/courier

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Ứng tuyển requester/courier |
| Actor | Requester hoặc Courier |
| Mục tiêu | Gửi yêu cầu tham gia chatbox theo vai trò |
| Tiền điều kiện | Chatbox chưa locked/archived; người dùng không phải owner; người dùng chưa là participant trong giao dịch |
| Luồng chính | Người dùng chọn role và nhập introduction note; frontend gọi `POST /api/transactions/{id}/apply`; backend kiểm tra role, điểm requester, xung đột requester/courier, sau đó tạo join_request Message |
| Luồng thay thế | Nếu requester không đủ điểm khả dụng hoặc role xung đột, backend trả 400 |
| Kết quả | Owner thấy join request trong Notification; applicant thấy sách trong Applying |

### 2.6.7. Use Case Owner chấp nhận hoặc xóa participant

Bảng 2.10. Bảng use case Owner chấp nhận hoặc xóa participant

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Owner chấp nhận hoặc xóa participant |
| Actor | Owner |
| Mục tiêu | Quản lý requester/courier trong chatbox |
| Tiền điều kiện | Người thao tác là owner của transaction; chatbox chưa locked |
| Luồng chính | Owner approve join request hoặc gọi endpoint accept/kick; backend cập nhật `requester_id` hoặc `courier_id`, thay đổi trạng thái message và thêm notification join/kicked |
| Luồng thay thế | Nếu owner_id không khớp hoặc applicant chưa gửi join request, backend trả 403/400 |
| Kết quả | Participant được vào chatbox hoặc bị gỡ khỏi chatbox; confirmation state được reset khi leave/kick |

### 2.6.8. Use Case Chat và thông báo

Bảng 2.11. Bảng use case Chat và thông báo

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Chat và thông báo |
| Actor | Owner, requester, courier đã được chấp nhận |
| Mục tiêu | Trao đổi thông tin và theo dõi sự kiện giao dịch |
| Tiền điều kiện | Người dùng là participant của transaction |
| Luồng chính | Frontend gọi `GET /messages`, `POST /messages`, `GET /application-stats`, `GET /activity/unread`; backend lọc message theo quyền xem và tab |
| Luồng thay thế | Người không phải participant truy cập chatbox sẽ bị backend trả 403 |
| Kết quả | Tin nhắn chat hiển thị trong Chatbox; join/kick/leave/confirmation hiển thị trong Notification |

### 2.6.9. Use Case Xác nhận giao nhận trực tiếp

Bảng 2.12. Bảng use case Xác nhận giao nhận trực tiếp

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Xác nhận giao nhận trực tiếp |
| Actor | Owner và requester |
| Mục tiêu | Hoàn tất giao dịch không có courier |
| Tiền điều kiện | Transaction có requester, không có courier, chưa archived |
| Luồng chính | Một bên tạo notification `confirm_direct_handoff`; bên còn lại approve; backend gọi logic xác nhận meeting với cặp owner-requester, đặt owner_confirmed và requester_confirmed |
| Luồng thay thế | Confirmation hết hạn sau 60 giây nếu không được approve |
| Kết quả | Hệ thống cộng/trừ điểm, đặt points_applied, archived và Book.available=False |

### 2.6.10. Use Case Xác nhận giao nhận qua courier

Bảng 2.13. Bảng use case Xác nhận giao nhận qua courier

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Xác nhận giao nhận qua courier |
| Actor | Owner, courier, requester |
| Mục tiêu | Hoàn tất giao dịch qua hai chặng giao nhận |
| Tiền điều kiện | Transaction có requester và courier |
| Luồng chính | Owner/courier xác nhận chặng owner-courier trước; hệ thống locked chatbox và đặt owner_confirmed. Sau đó courier/requester xác nhận chặng giao tới requester; hệ thống đặt requester_confirmed |
| Luồng thay thế | Nếu requester-courier xác nhận trước owner-courier, backend trả lỗi owner handoff must be confirmed first |
| Kết quả | Owner cộng 10 hoặc 5 điểm, requester trừ 10 hoặc 5 điểm, courier cộng 2 điểm |

### 2.6.11. Use Case Gia hạn sách cho mượn

Bảng 2.14. Bảng use case Gia hạn sách cho mượn

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Gia hạn sách cho mượn |
| Actor | Owner |
| Mục tiêu | Đưa lại một sách `loan` đã hoàn tất lên danh sách mới |
| Tiền điều kiện | Book có exchange_mode `loan`, transaction đã archived, người thao tác là owner |
| Luồng chính | Frontend hiển thị nút Renew trong Archive; owner gọi `POST /api/books/{book_id}/renew`; backend clone Book thành listing mới và mở transaction mới |
| Luồng thay thế | Nếu sách không phải loan hoặc chưa archived, backend trả 400 |
| Kết quả | Listing mới xuất hiện như một sách loan độc lập, lịch sử cũ giữ nguyên |

### 2.6.12. Use Case Theo dõi unread và activity

Bảng 2.15. Bảng use case Theo dõi unread và activity

| Nội dung | Mô tả |
| --- | --- |
| Tên Use Case | Theo dõi unread và activity |
| Actor | Thành viên |
| Mục tiêu | Biết tin nhắn/thông báo mới trong dropdown, chatbox và notification |
| Tiền điều kiện | Người dùng đã đăng nhập |
| Luồng chính | Layout polling `/api/members/{id}/messages`, `/api/activity/unread`; khi mở dropdown hoặc tab, frontend gọi `POST /api/activity` để cập nhật last_timestamp |
| Luồng thay thế | Nếu network lỗi ngắn hạn, UI giữ dữ liệu hiện tại và thử lại trong vòng polling sau |
| Kết quả | Badge unread giảm sau khi người dùng xem message scope tương ứng |

# CHƯƠNG 3. THIẾT KẾ KIẾN TRÚC TỔNG THỂ

## 3.1. Mô hình kiến trúc hệ thống

Hệ thống sử dụng kiến trúc client-server đơn giản:

- Client là ứng dụng SvelteKit chạy trong trình duyệt.
- Server là FastAPI application trong `backend/main.py`.
- Database là SQLite file `db.sqlite3`.
- File tĩnh được phục vụ qua FastAPI mount `/pic` và `/avatar`.
- Phiên đăng nhập được lưu ở `localStorage` bằng hai key `httt_token` và `httt_member`.

Kiến trúc này phù hợp với prototype vì giảm số lượng thành phần triển khai, dễ chạy cục bộ, dễ demo và toàn bộ business rule backend nằm trong một file.

## 3.2. Sơ đồ kiến trúc tổng thể

{{ARCHITECTURE_DIAGRAM}}

## 3.3. Sơ đồ luồng dữ liệu DFD

### 3.3.1. DFD mức ngữ cảnh

{{DFD_CONTEXT_DIAGRAM}}

### 3.3.2. DFD mức 0

{{DFD_LEVEL0_DIAGRAM}}

DFD mức 0 chia hệ thống thành năm tiến trình chính: quản lý tài khoản/hồ sơ, quản lý danh mục sách, quản lý chatbox/ứng tuyển, xác nhận giao nhận/cập nhật điểm và theo dõi hoạt động/thông báo. Các kho dữ liệu tương ứng là Member, Book, ExchangeTransaction, Message và ActivityTracking.

### 3.3.3. Phân rã Tiến trình 1.0 - Quản lý tài khoản và hồ sơ

{{DFD_ACCOUNT_PROFILE_DIAGRAM}}

Tiến trình này bao gồm đăng ký, đăng nhập, xác thực token và cập nhật hồ sơ. Backend tự triển khai JWT bằng base64url, HMAC SHA-256 và payload chứa `sub`, `email`, `exp`. Password được hash bằng PBKDF2-HMAC-SHA256 với salt ngẫu nhiên.

### 3.3.4. Phân rã Tiến trình 2.0 - Quản lý danh mục sách

{{DFD_BOOK_CATALOG_DIAGRAM}}

Khi owner tạo sách, backend đồng thời tạo transaction mở và message hệ thống. Điều này khiến mỗi sách khả dụng luôn có một không gian giao dịch để applicant gửi join request, owner quản lý participant và các bên trao đổi.

### 3.3.5. Phân rã Tiến trình 3.0 - Quản lý chatbox và ứng tuyển vai trò

{{DFD_TRANSACTION_CHATBOX_DIAGRAM}}

Chatbox là trung tâm điều phối giao dịch. Trước khi được accepted, applicant chỉ gửi được join request và xem thông tin sách. Sau khi accepted, participant có thể xem chatbox, notification, gửi message, nhận unread count và tham gia confirmation flow.

### 3.3.6. Phân rã Tiến trình 4.0 - Xác nhận giao nhận và cập nhật điểm

{{DFD_CONFIRMATION_POINTS_DIAGRAM}}

Điểm chỉ thay đổi khi `owner_confirmed=True` và `requester_confirmed=True`. Với giao trực tiếp, hai cờ có thể được đặt cùng lúc. Với courier, owner-courier handoff phải hoàn tất trước khi courier-requester delivery được xác nhận.

# CHƯƠNG 4. THIẾT KẾ KỸ THUẬT CHI TIẾT

## 4.1. Thiết kế cơ sở dữ liệu

Cơ sở dữ liệu được khai báo bằng SQLModel trong `backend/main.py`. Các class có `table=True` là bảng persistent thực tế. Các class còn lại như `AuthRequest`, `ApplyRequest`, `ChatMessageCreate`, `RoleDecision` là payload model cho API.

Database file mặc định là `sqlite:///db.sqlite3`. Khi backend startup, `SQLModel.metadata.create_all(engine)` tạo bảng nếu chưa tồn tại, sau đó `migrate_schema()` cập nhật một số cột cho database prototype cũ.

## 4.2. Sơ đồ ERD

{{ERD_DIAGRAM}}

## 4.3. Đặc tả chi tiết các bảng dữ liệu

### 4.3.1. Bảng Member

Bảng 4.1. Bảng dữ liệu Member

| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| --- | --- | --- |
| id | Optional[int], PK | Mã định danh thành viên |
| name | str | Tên hiển thị |
| email | str | Email đăng nhập, được chuẩn hóa lowercase |
| password_hash | str | Salt và hash password dạng `salt:digest` |
| points | int | Điểm hiện có của thành viên, mặc định 20 |
| gender | str | `male` hoặc `female`, dùng cho profile/avatar mặc định |
| age | int | Tuổi, backend giới hạn 1-120 |
| avatar_path | str | Đường dẫn avatar public trong `/avatar/*` |
| biography | str | Mô tả cá nhân |

### 4.3.2. Bảng Book

Bảng 4.2. Bảng dữ liệu Book

| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| --- | --- | --- |
| id | Optional[int], PK | Mã định danh sách |
| owner_id | int, FK Member.id | Chủ sở hữu sách |
| title | str | Tên sách |
| genre | str | Thể loại |
| author | str | Tác giả |
| description | str | Mô tả thêm |
| publication_year | int | Năm xuất bản |
| condition | str | Tình trạng sách: Like new, Good, Used, Fair hoặc giá trị nhập khác |
| exchange_mode | str | `permanent` hoặc `loan` |
| available | bool | Sách còn khả dụng hay đã hoàn tất giao dịch |
| picture_path | str | Đường dẫn ảnh sách trong `/pic/*` |

### 4.3.3. Bảng ExchangeTransaction

Bảng 4.3. Bảng dữ liệu ExchangeTransaction

| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| --- | --- | --- |
| id | Optional[int], PK | Mã giao dịch/chatbox |
| book_id | int, FK Book.id | Sách được giao dịch |
| owner_id | int, FK Member.id | Chủ sách |
| exchange_mode | str | Snapshot hình thức giao dịch từ Book |
| requester_id | Optional[int], FK Member.id | Thành viên được chấp nhận nhận/mượn sách |
| courier_id | Optional[int], FK Member.id | Thành viên được chấp nhận giao sách |
| owner_confirmed | bool | Owner đã hoàn tất chặng giao phù hợp |
| requester_confirmed | bool | Requester đã nhận sách |
| locked | bool | Chatbox đã khóa thay đổi participant sau khi bắt đầu giao nhận |
| points_applied | bool | Điểm đã được cộng/trừ hay chưa |
| archived | bool | Giao dịch đã hoàn tất và chuyển sang archive |

### 4.3.4. Bảng Message

Bảng 4.4. Bảng dữ liệu Message

| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| --- | --- | --- |
| message_id | Optional[int], PK | Mã tin nhắn/thông báo |
| user_id | int, FK Member.id | Người tạo message |
| transaction_id | int, FK transactions.id | Chatbox chứa message |
| message | str | Nội dung hiển thị |
| applied_role | str | Vai trò gắn với message: owner, requester, courier |
| notification_type | Optional[str] | Loại notification: join_request, kicked, leave, join, confirm_* hoặc null |
| approver_id | Optional[int], FK Member.id | Người cần approve notification |
| approver_role | Optional[str] | Vai trò cần approve |
| accepted | bool | Message đã được accepted/visible theo ngữ cảnh |
| timestamp | datetime | Thời điểm tạo message theo UTC |

### 4.3.5. Bảng ActivityTracking

Bảng 4.5. Bảng dữ liệu ActivityTracking

| Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| --- | --- | --- |
| id | Optional[int], PK | Mã tracking |
| member_id | int, FK Member.id | Thành viên được tracking |
| transaction_id | Optional[int], FK transactions.id | Giao dịch tương ứng; null với dropdown |
| tab | str | `dropdown`, `chatbox` hoặc `notification` |
| last_timestamp | datetime | Mốc thời gian gần nhất người dùng đã xem scope đó |

## 4.4. Đặc tả API Backend

Bảng 4.6. Bảng đặc tả API chính

| Method | Endpoint | Chức năng | Ghi chú nghiệp vụ |
| --- | --- | --- | --- |
| GET | `/api/health` | Health check | Trả `{"ok": true}` |
| POST | `/api/auth/register` | Đăng ký | Tạo Member, hash password, cấp token |
| POST | `/api/auth/login` | Đăng nhập | Kiểm tra password hash |
| GET | `/api/auth/me` | Lấy phiên hiện tại | Cần Authorization bearer token |
| GET | `/api/members` | Danh sách thành viên | Có derived field `is_courier` |
| GET | `/api/members/{id}/profile` | Hồ sơ công khai | Trả member + books |
| PUT | `/api/members/{id}/profile` | Sửa hồ sơ | Chỉ owner profile được sửa |
| GET | `/api/members/{id}/request-budget` | Điểm requester khả dụng | Tính reserved points từ request pending/accepted |
| GET | `/api/members/{id}/messages` | Dropdown messages | Trả visible messages mới nhất, loại trừ message của chính mình |
| GET | `/api/members/{id}/applications` | Pending applications | Dùng cho shelf Applying |
| GET | `/api/books` | Danh sách sách | Trả kèm owner_name, owner_email |
| POST | `/api/books` | Tạo sách | Tạo Book + Transaction + Message |
| PUT | `/api/books/{id}` | Cập nhật sách | Chỉ owner sách được sửa |
| DELETE | `/api/books/{id}` | Xóa sách | Chỉ xóa khi chưa có participant và chưa locked/archived |
| POST | `/api/books/{id}/renew` | Renew loan | Clone sách loan archived thành listing mới |
| GET | `/api/transactions` | Danh sách transaction | Trả readable names và point deltas |
| POST | `/api/transactions` | Mở/lấy chatbox | Tái sử dụng transaction active nếu có |
| GET | `/api/transactions/{id}/messages` | Xem message chatbox | Chỉ participant được xem |
| POST | `/api/transactions/{id}/messages` | Gửi chat message | Chỉ participant accepted được gửi |
| POST | `/api/transactions/{id}/apply` | Ứng tuyển role | Chặn owner, xung đột role, thiếu điểm |
| POST | `/api/transactions/{id}/accept` | Owner accept | Cập nhật requester/courier |
| POST | `/api/transactions/{id}/kick` | Owner kick | Gỡ requester/courier và reset confirmation |
| POST | `/api/transactions/{id}/leave` | Participant leave | Requester/courier rời chatbox |
| POST | `/api/transactions/{id}/withdraw-application` | Rút đơn | Xóa join_request pending |
| GET | `/api/transactions/{id}/application` | Lấy đơn của tôi | Dùng để sync selected role |
| GET | `/api/transactions/{id}/application-stats` | Thống kê applicant | Count requester/courier pending và accepted |
| POST | `/api/transactions/{id}/notifications` | Tạo notification | Hỗ trợ confirm handoff/delivery |
| POST | `/api/transactions/{id}/notifications/{message_id}/approve` | Approve notification | Có timeout 60 giây cho confirm notification |
| POST | `/api/activity` | Đánh dấu đã xem | Cập nhật ActivityTracking |
| GET | `/api/activity/unread` | Đếm unread | Dùng cho dropdown/chatbox/notification badges |
| POST | `/api/demo-seed` | Seed demo data | Tạo sample members/books nếu database rỗng |

## 4.5. Luồng xử lý nghiệp vụ trọng yếu

### 4.5.1. Tính điểm theo exchange mode

Hàm `points_for_mode` là điểm quyết định mapping nghiệp vụ:

- `permanent`: 10 điểm.
- `loan`: 5 điểm.
- Giá trị khác bị từ chối bằng HTTP 400.

Khi transaction hoàn tất, `complete_transaction_if_ready` cộng điểm cho owner, trừ điểm requester và cộng 2 điểm cho courier nếu có.

### 4.5.2. Tính điểm khả dụng của requester

Điểm khả dụng không chỉ là `Member.points`. Backend còn tính điểm đã bị giữ bởi:

- Các transaction mà member đã là requester nhưng chưa applied points và chưa archived.
- Các join request requester đang pending trong transaction chưa locked/archived.

Công thức:

`available_points = member.points - reserved_points`

Requester chỉ được ứng tuyển nếu `available_points >= required_points`.

### 4.5.3. Confirmation timeout

Confirmation notification thuộc các loại `confirm_direct_handoff`, `confirm_handoff`, `confirm_delivered` có thời hạn 60 giây. Nếu quá hạn, backend xóa approver information và frontend hiển thị trạng thái expired. Quy tắc này giảm rủi ro người dùng approve một yêu cầu xác nhận quá cũ.

### 4.5.4. Lock và archive

Khi bắt đầu xác nhận giao nhận vật lý, `lock_transaction` đặt `locked=True` và xóa join request. Sau khi đủ xác nhận:

- `points_applied=True`
- `archived=True`
- `Book.available=False`
- Owner/requester/courier points được cập nhật

Điều này bảo vệ transaction khỏi thay đổi participant giữa quá trình giao nhận.

Sau khi archived, transaction không biến mất khỏi trải nghiệm người dùng. Frontend đưa các giao dịch hoàn tất có liên quan đến member vào section Archive trên `/books`; khi mở lại, chatbox chuyển sang trạng thái read-only và hiển thị thông tin vai trò cùng biến động điểm. Vì vậy Archive hoạt động như một lớp transaction record: các bên có thể đối chiếu ai là owner/requester/courier, hình thức trao đổi nào đã hoàn tất và điểm đã cộng/trừ như thế nào.

# CHƯƠNG 5. THIẾT KẾ GIAO DIỆN NGƯỜI DÙNG - UI/UX

## 5.1. Nguyên tắc thiết kế giao diện

Giao diện được tổ chức theo luồng làm việc của thành viên câu lạc bộ sách:

- Sau đăng nhập, màn hình chính là shelf/dashboard, không phải landing page.
- Sách được chia nhóm theo trạng thái quan hệ với người dùng: My books, Accepted, Applying, Available, Archive.
- Archive không chỉ là danh sách sách cũ; đây là lớp record giao dịch read-only giúp thành viên xem lại các giao dịch đã hoàn tất và đối chiếu biến động điểm.
- Mỗi sách dẫn tới detail page với các tab có ý nghĩa rõ ràng: Book info, Chatbox, Notification.
- Các hành động nguy hiểm như delete và renew dùng ConfirmModal để tránh thao tác nhầm.
- Icon từ `@lucide/svelte` giúp button ngắn gọn: Edit, Delete, Renew, Back, Send, Profile, Notification, Leave.
- UI ưu tiên khả năng quét nhanh: card sách có title, author, genre/condition, exchange mode và owner.
- Polling định kỳ giúp người dùng thấy trạng thái mới mà không cần reload thủ công.

## 5.2. Danh sách màn hình chính

Bảng 5.1. Bảng danh sách màn hình chính

| STT | Màn hình | Route | Mô tả |
| --- | --- | --- | --- |
| 1 | Login/Register | `/login` | Chuyển đổi giữa đăng nhập và đăng ký; lưu session sau khi thành công |
| 2 | Books dashboard | `/books` | Hiển thị My books, Accepted, Applying, Available, Archive; Archive là record giao dịch hoàn tất và hỗ trợ tìm kiếm/lọc |
| 3 | Book detail | `/books/[id]` | Hiển thị thông tin sách, form ứng tuyển, chatbox, notification, participant panel |
| 4 | New/Edit book | `/books/new` | Tạo hoặc sửa listing sách, upload ảnh, chọn permanent/loan |
| 5 | Profile | `/profile/[id]` | Xem hồ sơ, điểm, sách đã đăng; owner profile có thể sửa hồ sơ và avatar |
| 6 | Global layout/header | `+layout.svelte` | Hiển thị brand, điểm, điểm khả dụng, dropdown messages, profile/logout |

## 5.3. Đặc tả kiểm soát giao diện

Bảng 5.2. Bảng đặc tả kiểm soát giao diện

| Thành phần | Quy định |
| --- | --- |
| Nút New book | Hiển thị trong My books, điều hướng `/books/new?mode=new` |
| Nút Edit | Chỉ xuất hiện trên sách thuộc My books |
| Nút Delete | Chặn nếu sách có requester/courier trong chatbox; mở modal hướng dẫn mở chatbox |
| Nút Renew | Chỉ xuất hiện với archived loan book mà người hiện tại là owner |
| Archive section | Hiển thị các transaction archived liên quan đến người dùng như record minh bạch, kèm nhãn Archived và biến động điểm |
| Application form | Chỉ hiển thị với người không phải owner, chưa accepted, sách available và chatbox chưa locked |
| Role toggle | Cho phép chọn requester hoặc courier trước khi apply |
| Request budget panel | Hiển thị điểm khả dụng và điểm cần thiết khi role requester |
| Chatbox tab | Chỉ hiển thị với participant accepted |
| Notification tab | Chỉ hiển thị với participant accepted |
| Approve notification button | Chỉ bật nếu member hiện tại là approver đúng id và role, notification chưa expired |
| Leave button | Chỉ bật với requester/courier accepted và transaction chưa locked |
| Remove requester/courier | Chỉ owner thấy trong participant panel |
| Archived read-only room | Khi mở transaction archived, chatbox không cho thao tác mới và hiển thị thay đổi điểm của owner/requester/courier |
| Unread badge | Hiển thị trên header dropdown, Chatbox tab và Notification tab |

## 5.4. Thiết kế component

### 5.4.1. ListingSection

`ListingSection.svelte` là component generic dùng để hiển thị các nhóm sách. Component nhận danh sách item, hàm `getBook`, snippet render card, empty text, action snippet và page size. Nó cung cấp sẵn:

- Search theo title, author, genre, description, year, condition, exchange mode, owner name, owner email và available/unavailable.
- Filter theo condition, year range, exchange mode, owner.
- Pagination mặc định 5 item/trang.
- Reset page về 1 khi filter/search đổi.

### 5.4.2. ConfirmModal

`ConfirmModal.svelte` dùng cho delete, renew và thông báo không thể delete. Component hỗ trợ tone `default` hoặc `danger`, busy state, Escape key để hủy, backdrop button và transition fade/scale.

### 5.4.3. Layout realtime state

`+layout.svelte` đồng bộ state header mỗi 1.8 giây:

- Refresh member qua `/api/auth/me`.
- Tải message dropdown qua `/api/members/{id}/messages`.
- Tải unread qua `/api/activity/unread`.
- Tải request budget qua `/api/members/{id}/request-budget`.

Khi mở dropdown, frontend gọi `POST /api/activity` với tab `dropdown` để đánh dấu đã xem.

# CHƯƠNG 6. KẾ HOẠCH KIỂM THỬ VÀ TRIỂN KHAI

## 6.1. Mục tiêu kiểm thử

Kiểm thử nhằm đảm bảo các luồng nghiệp vụ chính hoạt động đúng: đăng ký/đăng nhập, đăng sách, tìm kiếm/lọc, ứng tuyển role, owner accept/kick, chat, notification, xác nhận giao nhận, cập nhật điểm, archive và renew loan. Vì hệ thống có nhiều điều kiện vai trò, kiểm thử cần tập trung vào quyền thao tác và trạng thái transaction.

## 6.2. Phạm vi kiểm thử

Phạm vi bao gồm:

- API backend trong `backend/main.py`.
- Giao diện Svelte trong các route `/login`, `/books`, `/books/new`, `/books/[id]`, `/profile/[id]`.
- Dữ liệu SQLite được tạo mới hoặc demo-seed.
- Upload ảnh sách/avatar.
- Token/session frontend.
- Polling và unread badge.

## 6.3. Phương pháp kiểm thử

- Kiểm thử chức năng bằng thao tác UI end-to-end.
- Kiểm thử API bằng FastAPI docs hoặc HTTP client.
- Kiểm thử dữ liệu bằng kiểm tra SQLite records sau mỗi luồng.
- Kiểm thử role/permission bằng nhiều tài khoản demo.
- Kiểm thử negative case bằng dữ liệu thiếu điểm, role xung đột, confirmation expired, owner sai.

## 6.4. Kịch bản kiểm thử

Bảng 6.1. Bảng kịch bản kiểm thử

| Mã TC | Chức năng | Dữ liệu kiểm thử | Kết quả mong đợi |
| --- | --- | --- | --- |
| TC01 | Đăng ký | Name/email/password hợp lệ | Tạo member, points=20, trả token |
| TC02 | Đăng ký trùng email | Email đã tồn tại | Backend trả 400 |
| TC03 | Đăng nhập đúng | Email/password đúng | Lưu token, vào `/books` |
| TC04 | Đăng nhập sai | Password sai | Backend trả 401 |
| TC05 | Cập nhật profile | Sửa name, age, biography, avatar | Profile cập nhật và session refresh |
| TC06 | Tạo sách permanent | FormData hợp lệ, exchange_mode=permanent | Tạo Book, Transaction và Message |
| TC07 | Tạo sách loan | FormData hợp lệ, exchange_mode=loan | Tạo Book loan và chatbox mở |
| TC08 | Sửa sách không phải owner | Member khác gọi PUT | Backend trả 403 |
| TC09 | Xóa sách chưa có participant | Owner xóa sách mới | Book, transaction, messages liên quan bị xóa |
| TC10 | Xóa sách có participant | Sách đã có requester/courier | UI chặn và backend trả lỗi nếu gọi trực tiếp |
| TC11 | Search/filter | Lọc theo condition/year/owner | ListingSection chỉ hiện item phù hợp |
| TC12 | Requester apply đủ điểm | Member có đủ available points | Tạo join_request |
| TC13 | Requester apply thiếu điểm | Member có nhiều request pending vượt điểm | Backend trả 400 |
| TC14 | Courier apply | Member chọn courier | Tạo join_request courier |
| TC15 | Owner accept requester | Owner approve join_request | requester_id cập nhật, requester thấy Chatbox |
| TC16 | Owner accept courier | Owner approve courier | courier_id cập nhật, courier thấy Chatbox |
| TC17 | Chat message | Participant gửi message | Message xuất hiện cho các participant |
| TC18 | Non-participant xem chat | Member không accepted gọi GET messages | Backend trả 403 |
| TC19 | Owner kick requester | Owner xóa requester | requester_id null, confirmation reset |
| TC20 | Participant leave | Requester/courier rời chatbox | Role bị gỡ, message leave được tạo |
| TC21 | Direct handoff | Owner/requester xác nhận | Cộng/trừ điểm, archived, Book.available=False |
| TC22 | Courier handoff đúng thứ tự | Owner-courier rồi courier-requester | Owner/requester/courier points đúng |
| TC23 | Courier delivery sai thứ tự | Requester-courier trước owner-courier | Backend trả 400 |
| TC24 | Confirmation expired | Không approve trong 60 giây | Notification expired, không cập nhật điểm |
| TC25 | Renew loan | Owner renew archived loan | Tạo Book và Transaction mới |
| TC26 | Unread dropdown | Có message mới từ người khác | Badge tăng, giảm sau khi mở dropdown |
| TC27 | Demo seed | Database rỗng gọi `/api/demo-seed` | Tạo sample members/books |

## 6.5. Kế hoạch triển khai

### 6.5.1. Môi trường triển khai

Bảng 6.2. Bảng môi trường triển khai

| Thành phần | Môi trường |
| --- | --- |
| Backend | Python, FastAPI, SQLModel, Uvicorn, SQLite |
| Backend port | `http://localhost:8000` |
| API docs | `http://localhost:8000/docs` |
| Database | `backend/db.sqlite3` hoặc file SQLite theo working directory chạy backend |
| Static files | `pic/` và `avatar/` |
| Frontend | Node.js, SvelteKit 5, Vite |
| Frontend port | `http://localhost:5173` |
| Session storage | Browser localStorage |

### 6.5.2. Các bước cài đặt và chạy hệ thống

Backend:

```bash
cd backend
uv run uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Sau khi chạy:

1. Mở `http://localhost:8000/docs` để kiểm tra API.
2. Mở `http://localhost:5173` để dùng frontend.
3. Nếu cần dữ liệu demo, gọi `POST /api/demo-seed`.
4. Đăng nhập bằng tài khoản demo hoặc đăng ký tài khoản mới.

### 6.5.3. Sao lưu và phục hồi dữ liệu

Vì dữ liệu nằm trong SQLite, sao lưu prototype có thể thực hiện bằng cách copy file `db.sqlite3` khi backend dừng hoặc khi không có ghi dữ liệu. Thư mục `pic/` và `avatar/` cũng cần được sao lưu cùng database vì database chỉ lưu đường dẫn file ảnh.

# CHƯƠNG 7. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 7.1. Kết quả đạt được

Hệ thống đã triển khai được một prototype hoàn chỉnh cho nghiệp vụ trao đổi và cho mượn sách trong câu lạc bộ. Backend một file vẫn bao phủ đầy đủ model dữ liệu, route API, xác thực, upload file, migration nhỏ, điểm thưởng, chatbox, notification và confirmation. Frontend SvelteKit triển khai được trải nghiệm theo vai trò, hỗ trợ dashboard sách, form quản lý sách, detail tab, profile và header realtime.

Điểm nổi bật của hệ thống là luồng transaction rõ ràng: mỗi sách có chatbox, người tham gia phải ứng tuyển và được owner chấp nhận, các bên chat/thông báo trong cùng ngữ cảnh, điểm chỉ cập nhật sau khi đủ xác nhận giao nhận. Thiết kế này giúp giảm rủi ro cộng/trừ điểm sai và tạo lịch sử minh bạch cho từng giao dịch.

## 7.2. Hạn chế của hệ thống

- Backend vẫn là một file lớn, tốt cho prototype nhưng khó bảo trì khi số route tăng.
- Frontend dùng polling thay vì WebSocket nên chưa tối ưu tài nguyên khi có nhiều người dùng.
- SQLite phù hợp cục bộ, chưa phù hợp triển khai đồng thời quy mô lớn.
- Chưa có unit test/integration test tự động trong repository.
- Chưa có vai trò quản trị hoặc moderation nội dung.
- Chưa có quy trình trả sách riêng cho loan sau khi người mượn sử dụng xong.
- JWT secret mặc định phù hợp local demo, cần cấu hình nghiêm túc khi triển khai thật.
- Upload file chưa có cơ chế resize, virus scan hoặc dọn file không dùng.

## 7.3. Hướng phát triển trong tương lai

- Tách backend thành module khi prototype trưởng thành: models, auth, books, transactions, messages, activity.
- Bổ sung test tự động cho điểm, confirmation, requester budget và permission.
- Thay polling bằng WebSocket hoặc Server-Sent Events cho chatbox và notification.
- Thêm quy trình return flow cho sách loan, gồm mốc trả sách và xác nhận hoàn trả.
- Bổ sung đánh giá uy tín thành viên sau giao dịch.
- Thêm moderation nhẹ cho sách và hồ sơ nếu câu lạc bộ cần kiểm soát nội dung.
- Chuyển database sang PostgreSQL khi triển khai nhiều người dùng.
- Bổ sung storage quản lý ảnh tốt hơn, ví dụ object storage hoặc cleanup job.
- Bổ sung audit log cho các thao tác điểm và participant.

# TÀI LIỆU THAM KHẢO

1. FastAPI Documentation. `https://fastapi.tiangolo.com/`
2. SQLModel Documentation. `https://sqlmodel.tiangolo.com/`
3. Svelte Documentation. `https://svelte.dev/docs`
4. SvelteKit Documentation. `https://svelte.dev/docs/kit`
5. SQLite Documentation. `https://www.sqlite.org/docs.html`
6. Mermaid Documentation. `https://mermaid.js.org/`
7. Source code dự án: `IDEA.md`, `backend/AGENTS.md`, `backend/main.py`, `frontend/src/lib/api.ts`, `frontend/src/routes/**`.
"""


def build_markdown() -> str:
    replacements = {
        "{{USE_CASE_DIAGRAM}}": diagram_block("use_case_overview.mmd", "Hình 2.1. Sơ đồ Use Case tổng quát của hệ thống"),
        "{{ARCHITECTURE_DIAGRAM}}": diagram_block("architecture.mmd", "Hình 3.1. Sơ đồ kiến trúc tổng thể của hệ thống"),
        "{{DFD_CONTEXT_DIAGRAM}}": diagram_block("dfd_context.mmd", "Hình 3.2. Sơ đồ DFD mức ngữ cảnh"),
        "{{DFD_LEVEL0_DIAGRAM}}": diagram_block("dfd_level0.mmd", "Hình 3.3. Sơ đồ DFD mức 0"),
        "{{DFD_ACCOUNT_PROFILE_DIAGRAM}}": diagram_block("dfd_account_profile.mmd", "Hình 3.4. Phân rã Tiến trình 1.0 - Quản lý tài khoản và hồ sơ"),
        "{{DFD_BOOK_CATALOG_DIAGRAM}}": diagram_block("dfd_book_catalog.mmd", "Hình 3.5. Phân rã Tiến trình 2.0 - Quản lý danh mục sách"),
        "{{DFD_TRANSACTION_CHATBOX_DIAGRAM}}": diagram_block("dfd_transaction_chatbox.mmd", "Hình 3.6. Phân rã Tiến trình 3.0 - Quản lý chatbox và ứng tuyển vai trò"),
        "{{DFD_CONFIRMATION_POINTS_DIAGRAM}}": diagram_block("dfd_confirmation_points.mmd", "Hình 3.7. Phân rã Tiến trình 4.0 - Xác nhận giao nhận và cập nhật điểm"),
        "{{ERD_DIAGRAM}}": diagram_block("erd.mmd", "Hình 4.1. Sơ đồ ERD của hệ thống"),
    }
    report = REPORT_TEMPLATE.replace("{date}", datetime.now().strftime("%d/%m/%Y"))
    for marker, value in replacements.items():
        report = report.replace(marker, value)
    return report.strip() + "\n"


def clean_inline(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def xml_escape(text: str) -> str:
    return html.escape(text, quote=False)


NAVIGATION_SECTION_SLUGS = {
    "muc_luc",
    "danh_muc_hinh_anh",
    "danh_muc_bang_bieu",
}


def ascii_slug(text: str) -> str:
    text = clean_inline(text).lower().replace("đ", "d").replace("Đ", "d")
    normalized = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "_", without_marks).strip("_")
    return slug or "anchor"


def normalize_key(text: str) -> str:
    return ascii_slug(text)


def figure_key(text: str) -> str | None:
    match = re.match(r"^(?:Hình|HÃ¬nh)\s+(\d+)\.(\d+)\.", clean_inline(text))
    if not match:
        return None
    return f"fig_{match.group(1)}_{match.group(2)}"


def table_key(text: str) -> str | None:
    match = re.match(r"^(?:Bảng|Báº£ng)\s+(\d+)\.(\d+)", clean_inline(text))
    if not match:
        return None
    return f"table_{match.group(1)}_{match.group(2)}"


def unique_anchor(preferred: str, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", preferred)
    if not base or not base[0].isalpha():
        base = f"a_{base}"
    base = base[:80].rstrip("_") or "anchor"
    anchor = base
    suffix = 2
    while anchor in used:
        trimmed = base[: max(1, 76 - len(str(suffix)))]
        anchor = f"{trimmed}_{suffix}"
        suffix += 1
    used.add(anchor)
    return anchor


def register_anchor(
    anchors: dict[str, int],
    used: set[str],
    preferred: str,
) -> str:
    anchor = unique_anchor(preferred, used)
    anchors[anchor] = len(anchors) + 1
    return anchor


def build_anchor_maps(lines: list[str]) -> dict:
    bookmark_ids: dict[str, int] = {}
    used: set[str] = set()
    heading_targets: dict[str, str] = {}
    figure_targets: dict[str, str] = {}
    table_targets: dict[str, str] = {}
    current_top_section = ""

    for raw_line in lines:
        line = raw_line.rstrip()
        heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = clean_inline(heading_match.group(2).strip())
            if level == 1:
                current_top_section = ascii_slug(heading_text)
            preferred = f"heading_{ascii_slug(heading_text)}"
            anchor = register_anchor(bookmark_ids, used, preferred)
            heading_targets[normalize_key(heading_text)] = anchor
            continue

        if current_top_section in NAVIGATION_SECTION_SLUGS:
            continue

        fig_key = figure_key(line)
        if fig_key and fig_key not in figure_targets:
            figure_targets[fig_key] = register_anchor(bookmark_ids, used, fig_key)
            continue

        tbl_key = table_key(line)
        if tbl_key and tbl_key not in table_targets:
            table_targets[tbl_key] = register_anchor(bookmark_ids, used, tbl_key)

    return {
        "bookmark_ids": bookmark_ids,
        "headings": heading_targets,
        "figures": figure_targets,
        "tables": table_targets,
    }


def navigation_target(text: str, section_slug: str, anchor_maps: dict) -> str | None:
    if section_slug == "muc_luc":
        item_text = re.sub(r"^\d+\.\s*", "", clean_inline(text).strip())
        key = normalize_key(item_text)
        if key in anchor_maps["headings"]:
            return anchor_maps["headings"][key]
        chapter_match = re.search(r"chuong_(\d+)", key)
        if chapter_match:
            prefix = f"chuong_{chapter_match.group(1)}"
            for heading_key, anchor in anchor_maps["headings"].items():
                if heading_key.startswith(prefix):
                    return anchor
        if "tai_lieu_tham_khao" in key:
            return anchor_maps["headings"].get("tai_lieu_tham_khao")
        return None

    if section_slug == "danh_muc_hinh_anh":
        key = figure_key(text)
        return anchor_maps["figures"].get(key or "")

    if section_slug == "danh_muc_bang_bieu":
        key = table_key(text)
        return anchor_maps["tables"].get(key or "")

    return None


def run(text: str, style: str = "") -> str:
    style_xml = ""
    if style == "bold":
        style_xml = "<w:rPr><w:b/></w:rPr>"
    elif style == "code":
        style_xml = '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Consolas"/><w:sz w:val="18"/></w:rPr>'
    return f'<w:r>{style_xml}<w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r>'


def hyperlink(text: str, anchor: str) -> str:
    return (
        f'<w:hyperlink w:anchor="{xml_escape(anchor)}" w:history="1">'
        '<w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr>'
        f'<w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r>'
        "</w:hyperlink>"
    )


def bookmark_start(anchor: str, bookmark_id: int) -> str:
    return f'<w:bookmarkStart w:id="{bookmark_id}" w:name="{xml_escape(anchor)}"/>'


def bookmark_end(bookmark_id: int) -> str:
    return f'<w:bookmarkEnd w:id="{bookmark_id}"/>'


def paragraph(
    text: str = "",
    style: str | None = None,
    run_style: str = "",
    bookmark: tuple[str, int] | None = None,
    hyperlink_anchor: str | None = None,
) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    display_text = clean_inline(text)
    content = hyperlink(display_text, hyperlink_anchor) if hyperlink_anchor else run(display_text, run_style)
    if bookmark:
        content = f"{bookmark_start(*bookmark)}{content}{bookmark_end(bookmark[1])}"
    return f"<w:p>{ppr}{content}</w:p>"


def page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def image_size(path: Path) -> tuple[int, int]:
    if path.suffix.lower() == ".png":
        with path.open("rb") as file:
            header = file.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Not a PNG file: {path}")
        return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    width = root.attrib.get("width", "1000")
    height = root.attrib.get("height", "600")
    return int(float(width)), int(float(height))


def image_paragraph(rel_id: str, name: str, image_id: int, width_px: int, height_px: int) -> str:
    max_width_emu = int(6.4 * 914400)
    width_emu = max_width_emu
    height_emu = int(width_emu * height_px / max(width_px, 1))
    return f"""
<w:p>
  <w:pPr><w:jc w:val="center"/></w:pPr>
  <w:r>
    <w:drawing>
      <wp:inline distT="0" distB="0" distL="0" distR="0">
        <wp:extent cx="{width_emu}" cy="{height_emu}"/>
        <wp:effectExtent l="0" t="0" r="0" b="0"/>
        <wp:docPr id="{image_id}" name="{xml_escape(name)}"/>
        <wp:cNvGraphicFramePr>
          <a:graphicFrameLocks noChangeAspect="1"/>
        </wp:cNvGraphicFramePr>
        <a:graphic>
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic>
              <pic:nvPicPr>
                <pic:cNvPr id="{image_id}" name="{xml_escape(name)}"/>
                <pic:cNvPicPr/>
              </pic:nvPicPr>
              <pic:blipFill>
                <a:blip r:embed="{rel_id}"/>
                <a:stretch><a:fillRect/></a:stretch>
              </pic:blipFill>
              <pic:spPr>
                <a:xfrm>
                  <a:off x="0" y="0"/>
                  <a:ext cx="{width_emu}" cy="{height_emu}"/>
                </a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
              </pic:spPr>
            </pic:pic>
          </a:graphicData>
        </a:graphic>
      </wp:inline>
    </w:drawing>
  </w:r>
</w:p>
"""


def table(rows: list[list[str]]) -> str:
    output = [
        "<w:tbl>",
        "<w:tblPr>",
        '<w:tblStyle w:val="TableGrid"/>',
        '<w:tblW w:w="0" w:type="auto"/>',
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        "</w:tblBorders>",
        "</w:tblPr>",
    ]
    for row_index, row in enumerate(rows):
        output.append("<w:tr>")
        for cell in row:
            shading = '<w:shd w:fill="D9EAF7"/>' if row_index == 0 else ""
            output.append(f"<w:tc><w:tcPr>{shading}</w:tcPr>{paragraph(cell, None, 'bold' if row_index == 0 else '')}</w:tc>")
        output.append("</w:tr>")
    output.append("</w:tbl>")
    return "".join(output)


def markdown_to_body_plain(markdown: str, image_rels: dict[str, dict]) -> str:
    lines = markdown.splitlines()
    anchor_maps = build_anchor_maps(lines)
    bookmark_ids = anchor_maps["bookmark_ids"]
    body: list[str] = []
    i = 0
    in_code = False
    code_lines: list[str] = []
    current_top_section = ""
    while i < len(lines):
        line = lines[i].rstrip()
        if line.strip() == "<!-- PAGEBREAK -->":
            body.append(page_break())
            i += 1
            continue
        if line.startswith("```"):
            if in_code:
                for code_line in code_lines:
                    body.append(paragraph(code_line, "CodeBlock", "code"))
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", line.strip())
        if image_match:
            image_path = image_match.group(2)
            rel = image_rels[image_path]
            body.append(
                image_paragraph(
                    rel["rel_id"],
                    Path(image_path).name,
                    rel["image_id"],
                    rel["width"],
                    rel["height"],
                )
            )
            i += 1
            continue
        if line.startswith("|"):
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].startswith("|"):
                raw = lines[i].strip()
                cells = [clean_inline(cell.strip()) for cell in raw.strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    rows.append(cells)
                i += 1
            if rows:
                body.append(table(rows))
            continue
        if line.startswith("# "):
            heading_text = line[2:].strip()
            body.append(paragraph(heading_text, "Title" if heading_text.startswith("TÀI LIỆU PHÂN TÍCH") else "Heading1"))
        elif line.startswith("## "):
            body.append(paragraph(line[3:].strip(), "Heading2"))
        elif line.startswith("### "):
            body.append(paragraph(line[4:].strip(), "Heading3"))
        elif line.startswith("#### "):
            body.append(paragraph(line[5:].strip(), "Heading3"))
        elif re.match(r"^(Hình|Bảng) \d", line):
            body.append(paragraph(line, "Caption"))
        elif line.startswith("- "):
            body.append(paragraph("• " + line[2:].strip(), "Normal"))
        elif re.match(r"^\d+\. ", line):
            body.append(paragraph(line.strip(), "Normal"))
        else:
            body.append(paragraph(line, "Normal"))
        i += 1
    return "".join(body)


def bookmark_tuple(anchor: str | None, bookmark_ids: dict[str, int]) -> tuple[str, int] | None:
    if not anchor:
        return None
    return (anchor, bookmark_ids[anchor])


def markdown_to_body(markdown: str, image_rels: dict[str, dict]) -> str:
    lines = markdown.splitlines()
    anchor_maps = build_anchor_maps(lines)
    bookmark_ids = anchor_maps["bookmark_ids"]
    body: list[str] = []
    i = 0
    in_code = False
    code_lines: list[str] = []
    current_top_section = ""

    while i < len(lines):
        line = lines[i].rstrip()
        if line.strip() == "<!-- PAGEBREAK -->":
            body.append(page_break())
            i += 1
            continue
        if line.startswith("```"):
            if in_code:
                for code_line in code_lines:
                    body.append(paragraph(code_line, "CodeBlock", "code"))
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if not line.strip():
            i += 1
            continue

        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", line.strip())
        if image_match:
            image_path = image_match.group(2)
            rel = image_rels[image_path]
            body.append(
                image_paragraph(
                    rel["rel_id"],
                    Path(image_path).name,
                    rel["image_id"],
                    rel["width"],
                    rel["height"],
                )
            )
            i += 1
            continue

        if line.startswith("|"):
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].startswith("|"):
                raw = lines[i].strip()
                cells = [clean_inline(cell.strip()) for cell in raw.strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    rows.append(cells)
                i += 1
            if rows:
                body.append(table(rows))
            continue

        target_anchor = None if line.startswith("#") else navigation_target(line, current_top_section, anchor_maps)
        if target_anchor:
            body.append(paragraph(line.strip(), "Normal", hyperlink_anchor=target_anchor))
            i += 1
            continue

        if line.startswith("# "):
            heading_text = line[2:].strip()
            current_top_section = ascii_slug(heading_text)
            heading_anchor = anchor_maps["headings"].get(normalize_key(heading_text))
            style = "Title" if normalize_key(heading_text).startswith("tai_lieu_phan_tich") else "Heading1"
            body.append(paragraph(heading_text, style, bookmark=bookmark_tuple(heading_anchor, bookmark_ids)))
        elif line.startswith("## "):
            heading_text = line[3:].strip()
            heading_anchor = anchor_maps["headings"].get(normalize_key(heading_text))
            body.append(paragraph(heading_text, "Heading2", bookmark=bookmark_tuple(heading_anchor, bookmark_ids)))
        elif line.startswith("### "):
            heading_text = line[4:].strip()
            heading_anchor = anchor_maps["headings"].get(normalize_key(heading_text))
            body.append(paragraph(heading_text, "Heading3", bookmark=bookmark_tuple(heading_anchor, bookmark_ids)))
        elif line.startswith("#### "):
            heading_text = line[5:].strip()
            heading_anchor = anchor_maps["headings"].get(normalize_key(heading_text))
            body.append(paragraph(heading_text, "Heading3", bookmark=bookmark_tuple(heading_anchor, bookmark_ids)))
        elif figure_key(line) or table_key(line):
            fig_anchor = anchor_maps["figures"].get(figure_key(line) or "")
            table_anchor = anchor_maps["tables"].get(table_key(line) or "")
            body.append(paragraph(line, "Caption", bookmark=bookmark_tuple(fig_anchor or table_anchor, bookmark_ids)))
        elif line.startswith("- "):
            body.append(paragraph("• " + line[2:].strip(), "Normal"))
        elif re.match(r"^\d+\. ", line):
            body.append(paragraph(line.strip(), "Normal"))
        else:
            body.append(paragraph(line, "Normal"))
        i += 1

    return "".join(body)


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman"/><w:sz w:val="24"/></w:rPr>
    <w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:sz w:val="32"/></w:rPr>
    <w:pPr><w:jc w:val="center"/><w:spacing w:before="240" w:after="240"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:sz w:val="28"/></w:rPr>
    <w:pPr><w:spacing w:before="360" w:after="180"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:sz w:val="26"/></w:rPr>
    <w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:i/><w:sz w:val="24"/></w:rPr>
    <w:pPr><w:spacing w:before="180" w:after="100"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Caption">
    <w:name w:val="Caption"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:i/><w:sz w:val="22"/></w:rPr>
    <w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="120"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="CodeBlock">
    <w:name w:val="Code Block"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr>
    <w:pPr><w:spacing w:after="0"/></w:pPr>
  </w:style>
  <w:style w:type="character" w:styleId="Hyperlink">
    <w:name w:val="Hyperlink"/>
    <w:basedOn w:val="DefaultParagraphFont"/>
    <w:uiPriority w:val="99"/>
    <w:unhideWhenUsed/>
    <w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr>
  </w:style>
</w:styles>
"""


def content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="svg" ContentType="image/svg+xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def doc_rels_xml(image_rels: dict[str, dict]) -> str:
    image_relationships = []
    for rel in image_rels.values():
        image_relationships.append(
            f'<Relationship Id="{rel["rel_id"]}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="media/{xml_escape(rel["target_name"])}"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  {''.join(image_relationships)}
</Relationships>
"""


def core_xml() -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>System Design Report - Book Exchange Club</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>
"""


def app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex OOXML generator</Application>
</Properties>
"""


def document_xml(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    {body}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def collect_image_rels(markdown: str) -> dict[str, dict]:
    image_paths = []
    for match in re.finditer(r"^!\[[^\]]*\]\(([^)]+)\)$", markdown, re.M):
        image_path = match.group(1)
        if image_path not in image_paths:
            image_paths.append(image_path)
    rels: dict[str, dict] = {}
    for index, image_path in enumerate(image_paths, start=2):
        source = OUT_DIR / image_path
        width, height = image_size(source)
        rels[image_path] = {
            "source": source,
            "rel_id": f"rId{index}",
            "image_id": index,
            "target_name": Path(image_path).name,
            "width": width,
            "height": height,
        }
    return rels


def write_docx(markdown: str, path: Path) -> None:
    image_rels = collect_image_rels(markdown)
    body = markdown_to_body(markdown, image_rels)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types_xml())
        docx.writestr("_rels/.rels", root_rels_xml())
        docx.writestr("word/document.xml", document_xml(body))
        docx.writestr("word/_rels/document.xml.rels", doc_rels_xml(image_rels))
        docx.writestr("word/styles.xml", styles_xml())
        docx.writestr("docProps/core.xml", core_xml())
        docx.writestr("docProps/app.xml", app_xml())
        for rel in image_rels.values():
            docx.write(rel["source"], f'word/media/{rel["target_name"]}')


def main() -> None:
    global REPORT_IMAGE_EXTENSION
    OUT_DIR.mkdir(exist_ok=True)
    ASSET_DIR.mkdir(exist_ok=True)
    DIAGRAM_SRC_DIR.mkdir(parents=True, exist_ok=True)

    for file_name, source in DIAGRAMS.items():
        (DIAGRAM_SRC_DIR / file_name).write_text(source.strip() + "\n", encoding="utf-8")
    render_diagram_images()
    if render_png_diagram_images():
        REPORT_IMAGE_EXTENSION = "png"

    markdown = build_markdown()
    REPORT_MD.write_text(markdown, encoding="utf-8-sig")
    write_docx(markdown, REPORT_DOCX)
    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {REPORT_DOCX}")
    print(f"Wrote {len(DIAGRAMS)} Mermaid sources to {DIAGRAM_SRC_DIR}")


if __name__ == "__main__":
    main()
