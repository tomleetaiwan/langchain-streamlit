# 關於本範例
本範例是使用 [Streamlit](https://streamlit.io/) 與 [Langchain](https://python.langchain.com/docs/get_started/introduction.html) 搭配 Azure OpenAI Service 實作的對話機器人，並依照 [Vector Similarity Search with Azure SQL database and OpenAI](https://devblogs.microsoft.com/azure-sql/vector-similarity-search-with-azure-sql-database-and-openai/) 一文的說明，將 [OpenAI 所提供的 Simple English Wikipedia 主要條目的 Embedding 向量資料](https://cdn.openai.com/API/examples/data/vector_database_wikipedia_articles_embedded.zip) 儲存於 Azure SQL Database 內，以對話機器人的方式對 Azure SQL Database 進行全文檢索，並採用餘弦近似比對的方式找出與 Simple English Wikipedia 內最相近的內容。 程式碼皆位於 src 資料夾內，其餘資料夾不包含程式碼，都與環境部屬相關。若目前尚未有 Azure OpenAI Service 與 LangChain 開發經驗，也可先透過此[中文快速上手 Notebook 加速學習](https://github.com/tomleetaiwan/azure_openai_quick_start)。 

**本範例僅是功能示範，將 OpenAI API Key 與 SQL Server 連接字串儲存於環境變數中並非符合資訊安全的作法，請勿直接使用於對外開放之 Microsoft Azure 環境。**

 ![使用者介面](/images/streamlit-app-ui.png)

## 環境準備

- 備妥 Microsoft Azure 訂閱帳號
- 依據 [Vector Similarity Search with Azure SQL database and OpenAI](https://devblogs.microsoft.com/azure-sql/vector-similarity-search-with-azure-sql-database-and-openai/) 備妥向量資料於 Azure SQL Database 內
- 已經申請核准建立妥 Azure OpenAI Service 資源
- 已經於 Azure AI Studio 內建立好以下模型之部署 (deployment)
    + gpt-35-turbo
    + text-embedding-ada-002        
- 備妥 Python 3.11 編輯與執行環境
- 備妥 以下 Python 套件
    + python-dotenv (1.0.0)
    + langchain (0.0.250)
    + openai (0.27.8)
    + tiktoken (0.4.0)
    + faiss-cpu (1.7.4)
    + streamlit (1.26.0)
    + streamlit-chat (0.1.1)
    + pyodbc (4.0.39)
    + sqlalchemy (2.0.19)
    + wikipedia (1.4.0)
    + pandas (2.0.3)

- 備妥 Docker 容器環境 (選用)
- 若在 Linux 環境進行開發，須備妥 [Microsoft ODBC 17 環境](https://learn.microsoft.com/zh-tw/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver16&tabs=alpine18-install%2Calpine17-install%2Cdebian8-install%2Credhat7-13-install%2Crhel7-offline#17)

所需的兩種模型，可點選 [Azure AI Studio](https://oai.azure.com/portal) 標示之 **Deployments** 選項，即可依序建立部署，請紀錄模型之部署名稱，後續需要輸入環境變數之中。

## 設定作業系統之環境變數
本範例採用了 Python dotenv 套件，環境變數也可以寫在 .env 檔案中，例如:

```bash
OPENAI_API_KEY=1234567890abcdef1234567890abcdef
OPENAI_API_BASE=https://<您的 Azure OpenAI 資源名稱>.openai.azure.com/
DEPLOYMENT_NAME=gpt-35-turbo
OPENAI_API_VERSION=2023-05-15
OPENAI_API_TYPE=azure
SQL_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=tcp:<資料庫伺服器名稱>.database.windows.net,1433;Database=openai;Uid=<登入帳號>;Pwd=<登入密碼>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=120;
```
Pyhotn dotenv 套件使用之 .env 檔案請置於 src 資料夾內。

## 單純在開發環境執行此程式碼

在命令列模式下切換至 /src 資料夾，並執行以下指令

```bash
streamlit run main.py
```
以瀏覽器開啟 http://localhost:8501/ 即可進行測試

## 建置 Container Image

### 以 "streamlit-app" 為標籤名稱建立 Container Image，例如

在命令列模式下切換至 /src ，也就是 Dockerfile 所在的資料夾，並執行以下指令
```bash
docker build -t streamlit-app:1 .
```

### 在本機執行與測試 Container Image，例如
```bash
docker run -dit --name streamlit-app -p 8501:8501 streamlit-app:1
```
以瀏覽器開啟 http://localhost:8501/ 即可進行測試


## 手動以容器方式部署於 Microsoft Azure

### 將 Container Image 送入 Azure Container Registry (ACR)
1. 登入 Azure Container Registry
```bash
az acr login --name <您的ACR名稱> 
```

2. 將目前本機的 Container Image streamlit-app:1 貼上未來存放在 Azure Container Registry 內並保有相同名稱的 Tag，可使用以下指令
```bash
docker tag streamlit-app:1 <您的ACR名稱>.azurecr.io/streamlit-app:1
```

3. 推送已標示標籤的 Container Image 至 Azure Container Registry
```bash
docker push <您的ACR名稱>.azurecr.io/streamlit-app:1
```
### 若要將 Container Image streamlit-app:1 部署於 Azure Kubernetes Service，並搭配 [Traefik 2 Ingress Controller](https://doc.traefik.io/traefik/) 與 TLS 憑證 Secrect 可參考以下方式

在命令列模式下切換至 /kubernetes 資料夾，並執行以下指令

```bash
kubectl apply -f streamlit-app.yaml
kubectl apply -f tls-traefik-ingress-name-route.yaml
```
### 若要將 Container Image streamlit-app:1 部署於 Azure Container Apps 可參考以下方式
```bash
az containerapp create --name ca-streamlitapp  --resource-group <您的資源群組> --environment <您的 Azure Container Apps 環境名稱> --image <您的ACR名稱>.azurecr.io/streamlit-app:1 --target-port 8501 --ingress external --registry-server <您的ACR名稱>.azurecr.io --query properties.configuration.ingress.fqdn
```
若順利部署完畢會顯示 URL 以供存取

## 以 Azure Developer CLI 自動化部署於 Microsoft Azure

[Azure Developer CLI](https://learn.microsoft.com/zh-tw/azure/developer/azure-developer-cli/overview) (azd) 是開放原始碼的命令列工具，可以簡化開發人員直接在雲端部署容器相關測試環境的複雜度。[安裝妥 Azure Developer CLI](https://learn.microsoft.com/zh-tw/azure/developer/azure-developer-cli/install-azd?tabs=winget-windows%2Cbrew-mac%2Cscript-linux&pivots=os-windows) 後，開發人員以下列指令登入

```bash
azd login
```

本 Repo 已經備妥相使用 Azure Developer CLI 部署應用程式所需之 Template，但不包含 Azure SQL database 與 Simple English Wikipedia OpenAI Embeddings 資料庫環境之建立 ，用戶備妥資料庫後；可使用以下指令建立雲端所需之測試環境，並將本程式以容器方式部署於 Azure Container Apps

```bash
azd up
```

若順利部署完畢會顯示 URL 以供存取，若要清除雲端所建立的資源，可使用以下指令

```bash
azd down
```

