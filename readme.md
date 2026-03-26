# BugSeek

BugSeek 鏄竴涓?AI 椹卞姩鐨勬祴璇曡川閲忓钩鍙帮紝鎻愪緵浠庨渶姹傛礊瀵熷埌 CI/CD 闆嗘垚鐨勫叏娴佺▼娴嬭瘯瑙ｅ喅鏂规銆?
## 椤圭洰缁撴瀯

```
BugSeek/
鈹溾攢鈹€ backend/           # 鍚庣椤圭洰锛團astAPI + Python锛?鈹溾攢鈹€ frontend/          # 鍓嶇椤圭洰锛圧eact + TypeScript + Ant Design锛?鈹斺攢鈹€ README.md
```

## 鎶€鏈爤

### 鍚庣
- FastAPI - Web 妗嗘灦
- PostgreSQL - 鏁版嵁搴?- SQLAlchemy - ORM
- JWT - 璁よ瘉
- prance - OpenAPI 鏂囨。瑙ｆ瀽
- Celery - 寮傛浠诲姟闃熷垪
- Redis - 娑堟伅闃熷垪鍜岀紦瀛?- Docker - 瀹瑰櫒鍖栭儴缃?
### 鍓嶇
- React 18 - UI 妗嗘灦
- TypeScript - 绫诲瀷瀹夊叏
- Ant Design 5 - UI 缁勪欢搴?- Vite - 鏋勫缓宸ュ叿
- Zustand - 鐘舵€佺鐞?- React Router - 璺敱绠＄悊

## 蹇€熷紑濮?
### 鍓嶆彁鏉′欢

- Docker 鍜?Docker Compose 宸插畨瑁?- Python 3.10+
- Node.js 18+

### 1. 鍚姩 PostgreSQL 鏁版嵁搴擄紙濡傛灉鏈惎鍔級

```bash
# 浣跨敤 Docker 鍚姩 PostgreSQL
docker run -d \
  --name bugseek-postgres \
  -e POSTGRES_DB=bugseek \
  -e POSTGRES_USER=bugseek \
  -e POSTGRES_PASSWORD=bugseek \
  -p 0.0.0.0:5432:5432 \
  postgres:15
```

### 1.5 瀹夎 pgvector 鎵╁睍锛堝繀闇€锛?
pgvector 鏄?PostgreSQL 鐨勫悜閲忕浉浼煎害鎼滅储鎵╁睍锛岀敤浜庝紭鍖栨柟妗?V2.0 鐨勫悜閲忕储寮曞姛鑳姐€?
#### 瀹夎姝ラ锛?
```bash
# 1. 杩涘叆 PostgreSQL 瀹瑰櫒
docker exec -it bugseek-postgres bash

# 2. 瀹夎缂栬瘧渚濊禆
apt-get update
apt-get install -y git build-essential postgresql-server-dev-15

# 3. 涓嬭浇骞剁紪璇?pgvector锛堢増鏈?v0.5.1锛?cd /tmp
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install

# 4. 楠岃瘉瀹夎
ls /usr/lib/postgresql/15/lib/vector.so

# 5. 鍚敤鎵╁睍
psql -U bugseek -d bugseek
CREATE EXTENSION IF NOT EXISTS vector;
\dx
# 搴旇鐪嬪埌锛歷ector | 0.5.1 | public
\q

# 6. 閫€鍑哄鍣?exit
```

#### 楠岃瘉瀹夎锛?
```bash
# 杩炴帴鏁版嵁搴撴祴璇?docker exec -it bugseek-postgres psql -U bugseek -d bugseek

# 鍒涘缓娴嬭瘯琛?CREATE TABLE test_vector (id serial, embedding vector(3));
INSERT INTO test_vector (embedding) VALUES ('[1,2,3]');
SELECT * FROM test_vector;
DROP TABLE test_vector;
```

**娉ㄦ剰**锛歱gvector 鎵╁睍鍙渶瑕佸畨瑁呬竴娆★紝瀹瑰櫒閲嶅惎鍚庝粛鐒舵湁鏁堛€?
### 2. 鍚姩 Redis锛堝鏋滄湭鍚姩锛?
```bash
# 浣跨敤 Docker 鍚姩 Redis锛堢鍙?6380锛屼笌鍏朵粬椤圭洰鐨?Redis 鍒嗗紑锛岄伩鍏嶅啿绐侊級
docker run -d \
  --name bugseek-redis \
  -p 0.0.0.0:6380:6380 \
  redis:7.0 \
  redis-server --port 6380
```
docker start bugseek-redis

**璇存槑**: Redis 浣跨敤绔彛 6380锛堟槧灏勫埌瀹瑰櫒鍐呯殑 6379锛夛紝涓庡叾浠栭」鐩殑 Redis锛堝 6379锛夊垎寮€锛岄伩鍏嶅啿绐併€?
### 3. 鍚姩 Celery Worker

```bash
cd backend

# 浣跨敤鍛戒护琛屽惎鍔?Celery Worker
celery -A app.celery_config worker --loglevel=info --pool=solo
```

**璇存槑**: Celery Worker 浼氳繛鎺ュ埌 Redis锛堢鍙?6380锛変綔涓烘秷鎭槦鍒楋紝澶勭悊寮傛浠诲姟銆?
**鍙傛暟璇存槑**:
- `-A app.celery_config`: 鎸囧畾 Celery 搴旂敤閰嶇疆妯″潡
- `worker`: 鍚姩 worker 杩涚▼
- `--loglevel=info`: 鏃ュ織绾у埆涓?info
- `--pool=solo`: 浣跨敤 solo 姹狅紙鍗曡繘绋嬶紝閫傚悎寮€鍙戠幆澧冿級

### 4. 鍚姩鍚庣鏈嶅姟

```bash
cd backend

# 鍒涘缓铏氭嫙鐜锛堝彲閫夛級
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 瀹夎渚濊禆
pip install -r requirements.txt

# 閰嶇疆鐜鍙橀噺
cp .env.example .env
# 缂栬緫 .env 鏂囦欢锛岄厤缃暟鎹簱杩炴帴绛変俊鎭?
# 鍒濆鍖栨暟鎹簱
python migrations/init_tables.py

# 鍚姩鏈嶅姟
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

鍚庣鏈嶅姟灏嗗湪 http://localhost:8000 鍚姩

API 鏂囨。锛歨ttp://localhost:8000/docs

### 4.1 鏁版嵁搴撳垵濮嬪寲璇存槑

褰撳墠椤圭洰鐨勬暟鎹簱鍒濆鍖栧彧淇濈暀涓€鏉¤矾寰勶細

```bash
cd backend
python migrations/init_tables.py
```

- `backend/migrations/init_tables.py` 鏄綋鍓嶅敮涓€鍙墽琛岀殑鍒濆鍖栧叆鍙ｃ€�
- `backend/migrations/init_schema.sql` 鏄笌鍏朵竴鑷寸殑 SQL 瀵煎嚭鏂囦欢锛屼究浜庡鏌ユ垨鍦ㄥ閮ㄧ幆澧冩墽琛屻€�
- `backend/migrations/generate_init_tables.py` 鐢ㄤ簬浠庡綋鍓嶇湡瀹?PostgreSQL 缁撴瀯鍙嶅皠骞堕噸鏂扮敓鎴愬垵濮嬪寲鑴氭湰銆€�
- 鍘熷厛闆舵暎鐨勬棫杩佺Щ鑴氭湰宸插綊妗ｅ埌 `backend/migrations/archived/`锛屼粎淇濈暀鍘嗗彶锛屼笉鍐嶄綔涓哄綋鍓嶅垵濮嬪寲鏂瑰紡銆€�

### 5. 鍚姩鍓嶇鏈嶅姟

```bash
cd frontend

# 瀹夎渚濊禆
npm install

# 鍚姩寮€鍙戞湇鍔″櫒
npm run dev
```

鍓嶇鏈嶅姟灏嗗湪 http://localhost:3000 鍚姩

## 鏈嶅姟绠＄悊

### 鏌ョ湅鏈嶅姟鐘舵€?
```bash
# 鏌ョ湅 Docker 瀹瑰櫒鐘舵€?docker ps

# 鏌ョ湅 Redis 鏃ュ織
docker logs -f bugseek-redis

# 鏌ョ湅 PostgreSQL 鏃ュ織
docker logs -f bugseek-postgres
```

### 鍋滄鏈嶅姟

```bash
# 鍋滄 Redis
docker stop bugseek-redis
docker rm bugseek-redis

# 鍋滄 PostgreSQL
docker stop bugseek-postgres
docker rm bugseek-postgres

# 鍋滄 Celery Worker锛堟寜 Ctrl+C锛?```

### 閲嶅惎鏈嶅姟

```bash
# 閲嶅惎 Redis
docker restart bugseek-redis

# 閲嶅惎 PostgreSQL
docker restart bugseek-postgres

# 閲嶅惎 Celery Worker
# 鍏堝仠姝紙鎸?Ctrl+C锛夛紝鐒跺悗閲嶆柊鎵ц鍚姩鍛戒护锛?cd backend
celery -A app.celery_config worker --loglevel=info --pool=solo
```

## 鍔熻兘妯″潡

### 宸插疄鐜?
#### 鐧诲綍娉ㄥ唽妯″潡
- 鐢ㄦ埛娉ㄥ唽
- 鐢ㄦ埛鐧诲綍
- 鑾峰彇鐢ㄦ埛淇℃伅
- 淇敼瀵嗙爜
- 鏇存柊鐢ㄦ埛淇℃伅
- 鐢ㄦ埛鐧诲嚭

#### 鎺ュ彛鏂囨。绠＄悊妯″潡
- 瀵煎叆鎺ュ彛鏂囨。锛圫wagger/OpenAPI锛?- 鏂囨。鍒楄〃灞曠ず
- 鏂囨。璇︽儏鏌ョ湅
- 鍒犻櫎鏂囨。

#### 鎺ュ彛瀹氫箟绠＄悊妯″潡
- 鎺ュ彛鍒楄〃灞曠ず
- 鎺ュ彛璇︽儏鏌ョ湅
- 鎺ュ彛鎼滅储
- 鎺ュ彛杩囨护锛堟寜鏂规硶锛?
#### 鏅鸿兘鍦烘櫙缁勮妯″潡
- 鎺ュ彛渚濊禆鍒嗘瀽锛堝熀浜庡垎缁勭殑寮傛鍒嗘瀽锛?- 涓氬姟閾捐矾璇嗗埆
- 鍦烘櫙鑷姩鐢熸垚
- 鍦烘櫙渚濊禆鍥惧彲瑙嗗寲
- 鍦烘櫙鎵ц锛堟敮鎸佸彉閲忎紶閫掞級

#### 妯″潡渚濊禆鍒嗘瀽妯″潡
- **鍩轰簬璧勬簮鐢熷懡鍛ㄦ湡鐨勬ā鍧楀唴閾捐矾鐢熸垚**
  - 璧勬簮鑱氱被锛氭寜 URL 璺緞璇嗗埆璧勬簮瀹炰綋
  - 鎿嶄綔鍒嗙被锛欳reator/Reader/Updater/Deleter/Action
  - 鐢熷懡鍛ㄦ湡閾捐矾锛歅OST 鈫?GET 鈫?PUT/PATCH 鈫?DELETE
  - 浼樺寲鏁堟灉锛氫粠 96,337 鏉￠摼璺紭鍖栧埌 5-8 鏉℃牳蹇冮摼璺?
- **鍩轰簬璧勬簮涓婁笅鏂囩殑妯″潡闂翠緷璧栧垎鏋愶紙閫氱敤绠楁硶锛?*
  - **绠楁硶鐗圭偣**锛?    - 鉁?楂樺害閫氱敤锛氶€傜敤浜庝换浣曞熀浜?OpenAPI/Swagger 瑙勮寖鐨?RESTful API 绯荤粺
    - 鉁?鏍稿績绠楁硶鎶借薄锛氬€掓帓绱㈠紩銆佽祫婧愪笂涓嬫枃鍒嗘瀽銆佸绾у尮閰嶇瓥鐣?    - 鉁?鍙厤缃寲锛氳涔夋槧灏勮〃銆佽祫婧愮被鍨嬪畾涔夈€佹潈閲嶇郴鏁板潎鍙畾鍒?    - 鉁?鏅鸿兘鍖栵細鏀寔鑷姩鎻愬彇璧勬簮绫诲瀷銆佹櫤鑳芥帹鑽愯涔夊埆鍚?    - 鉁?鎬ц兘浼樺寲锛氫粠 O(N虏) 浼樺寲鍒版帴杩?O(M) 鐨勭嚎鎬у鏉傚害
    - 鉁?楂樿川閲忥細鍙繚鐣欓珮缃俊搴︿緷璧栵紝閬垮厤缁勫悎鐖嗙偢
  
  - **閫傜敤绯荤粺**锛?    - 馃煝 **楂樺害閫傜敤**锛氱數鍟嗙郴缁燂紙Product, Order, Customer锛夈€丆RM 绯荤粺銆丒RP 绯荤粺
    - 馃煛 **涓瓑閫傜敤**锛氱ぞ浜ゅ钩鍙帮紙User, Post, Comment锛夈€佸井鏈嶅姟鏋舵瀯
    - 鉂?**涓嶉€傜敤**锛氭病鏈?API 鏂囨。瑙勮寖鐨勯仐鐣欑郴缁熴€侀潪 RESTful 绯荤粺锛圧PC/GraphQL锛?
  - **璋冩暣姝ラ**锛?    1. **瀹氫箟璇箟鏄犲皠琛?*锛堝繀濉級锛?       ```python
       semantic_map = {
           'Product': ['product', 'item', 'goods', 'sku', 'product_id'],
           'Order': ['order', 'purchase_order', 'transaction'],
           'Customer': ['customer', 'user', 'buyer', 'client'],
       }
       ```
    2. **鑷姩鎻愬彇璧勬簮绫诲瀷**锛堟帹鑽愶級锛?       ```python
       analyzer = ResourceContextAnalyzer(db)
       analyzer.auto_extract_resources_from_schemas(endpoints)
       ```
    3. **鏅鸿兘鎺ㄨ崘璇箟鍒悕**锛堝彲閫夛級锛?       ```python
       analyzer.infer_semantic_aliases('Product', field_names)
       ```
    4. **鍙€夛細璋冩暣鏉冮噸绯绘暟**锛堟牴鎹笟鍔￠渶姹傚井璋冿級

  - **鏍稿績绠楁硶娴佺▼**锛?    - 绗竴闃舵锛氶潤鎬佽涔夎В鏋愪笌绱㈠紩鏋勫缓锛堝€掓帓绱㈠紩锛?    - 绗簩闃舵锛氱敓浜ц€呴亶鍘嗕笌鍖归厤锛圤(1) 鏌ユ壘锛?    - 绗笁闃舵锛氳瘎鍒嗕笌杩囨护锛堝繀濉」 + Action 鎺ュ彛鍔犳潈锛?
  - **渚濊禆绫诲瀷鏍囪**锛?    - HARD锛氬己渚濊禆锛坰trength 鈮?0.8 鎴?Action 鎺ュ彛鎴栧繀濉」锛?    - SOFT锛氬急渚濊禆锛堝叾浠栨儏鍐碉級

  - **涓夎渚濊禆淇濈暀**锛氱‘淇濆叧閿笟鍔￠摼璺笉涓㈠け

### 寰呭疄鐜?
- 娴嬭瘯鑴氭湰鑷姩鐢熸垚
- Mock 鏈嶅姟绠＄悊
- 娴嬭瘯濂椾欢绠＄悊
- 娴嬭瘯鎶ュ憡鐢熸垚
- CI/CD 闆嗘垚
- 绮惧噯娴嬭瘯锛圱IA锛?- 璐ㄩ噺闂ㄧ

## Docker 鏈嶅姟璇存槑

### 鏈嶅姟鏋舵瀯

BugSeek 浣跨敤 Docker 绠＄悊浠ヤ笅鏈嶅姟锛?
| 鏈嶅姟 | 瀹瑰櫒鍚?| 绔彛 | 鐢ㄩ€?|
|------|--------|------|------|
| PostgreSQL | bugseek-postgres | 5432:5432 | 涓绘暟鎹簱 |
| Redis | bugseek-redis | 6380:6379 | Celery 浠诲姟闃熷垪 |

**Celery Worker** 閫氳繃鍛戒护琛岀洿鎺ヨ繍琛岋紙涓嶄娇鐢?Docker锛?
### 绔彛璇存槑

- **5432**: PostgreSQL 鏁版嵁搴?- **6380**: BugSeek Redis锛堟槧灏勫埌瀹瑰櫒鍐呯殑 6379锛屼笌鍏朵粬椤圭洰鐨?Redis 鍒嗗紑锛岄伩鍏嶅啿绐侊級
- **8000**: FastAPI 鍚庣鏈嶅姟
- **3000**: 鍓嶇鏈嶅姟

### 甯哥敤鍛戒护

```bash
# 鍚姩 Redis
docker start bugseek-redis

# 鍋滄 Redis
docker stop bugseek-redis

# 鍚姩 PostgreSQL
docker start bugseek-postgres

# 鍋滄 PostgreSQL
docker stop bugseek-postgres

# 鏌ョ湅 Redis 鏃ュ織
docker logs -f bugseek-redis

# 鏌ョ湅 PostgreSQL 鏃ュ織
docker logs -f bugseek-postgres

# 杩涘叆 Redis 瀹瑰櫒
docker exec -it bugseek-redis redis-cli

# 杩涘叆 PostgreSQL 瀹瑰櫒
docker exec -it bugseek-postgres psql -U bugseek -d bugseek
```

## 寮€鍙戣鏄?
### 鍚庣寮€鍙?
- API 璺敱瀹氫箟鍦?`backend/app/api/v1/` 鐩綍涓?
- 褰撳墠 SQLAlchemy 妯″瀷瀹氫箟鍦?`backend/app/platform/db/base.py`
- 鏁版嵁搴撹繛鎺ュ拰 Session 鍦?`backend/app/platform/db/session.py`
- 閰嶇疆鏂囦欢鍦?`backend/app/platform/config/settings.py`
- 渚濊禆娉ㄥ叆锛?`backend/app/dependencies.py`
### 鍓嶇寮€鍙?
- 椤甸潰缁勪欢锛歚frontend/src/pages/`
- 閫氱敤缁勪欢锛歚frontend/src/components/`
- 鐘舵€佺鐞嗭細`frontend/src/store/`
- API 鏈嶅姟锛歚frontend/src/services/`
- 绫诲瀷瀹氫箟锛歚frontend/src/types/`

## 鐜鍙橀噺

### 鍚庣鐜鍙橀噺锛?env锛?
```bash
# 鏁版嵁搴撻厤缃?DATABASE_URL=postgresql://bugseek:bugseek@localhost:5432/bugseek

# JWT 閰嶇疆
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Redis 閰嶇疆锛堢敤浜?Celery 寮傛浠诲姟闃熷垪锛岀鍙?6380锛?REDIS_URL=redis://localhost:6380/0

# 鏂囦欢涓婁紶閰嶇疆
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=10485760

# 鏃ュ織閰嶇疆
LOG_DIR=./logs
```

### 鍓嶇鐜鍙橀噺锛?env锛?
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 璁稿彲璇?
MIT

## Frontend Build And Deploy

- Frontend source is in `frontend/`.
- Production assets must be generated with `npm run build`.
- `frontend/dist/` is treated as a build artifact and should not be committed.
- See `docs/frontend_build_and_deploy.md` for the deployment flow.
