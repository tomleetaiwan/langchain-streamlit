#
#  執行方式 streamlit run main.py
#
import os
import json
import streamlit as st
import pandas as pd
import sqlalchemy as sa
import struct
from sqlalchemy import create_engine, event
from sqlalchemy.engine.url import URL
from azure import identity
from streamlit_chat import message
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai.chat_models.azure import AzureChatOpenAI
from langchain_openai.embeddings.azure import AzureOpenAIEmbeddings
from langchain_community.document_loaders import WikipediaLoader
from langchain.schema import (
    SystemMessage,
    HumanMessage,
    AIMessage
)

# 載入 Azure OpenAI Service API 相關資訊
load_dotenv()

# 設定呼叫 OpenAI API 所需連線資訊
chat_model = os.getenv("CHAT_DEPLOYMENT_NAME")
embeddings_model = os.getenv("EMBEDDINS_DEPLOYMENT_NAME")
api_ver = os.getenv("AZURE_OPENAI_API_VERSION")


# 建立 Azure OpenAI Chat 與 Embeddings 類別的實例
chat = AzureChatOpenAI(
    azure_deployment=chat_model,
    api_version=api_ver,
    temperature=0,
    max_tokens=2000,
    timeout=30,
    max_retries=2,
)

embeddings = AzureOpenAIEmbeddings(
    deployment=embeddings_model,
    api_version=api_ver,
    chunk_size = 16
)

# 以目前之 Microsoft Entra ID Credential 進行身分驗證
SQL_CONNECT_ERROR_MSG = ""
SQL_COPT_SS_ACCESS_TOKEN = 1256  # Connection option for access tokens, as defined in msodbcsql.h
TOKEN_URL = "https://database.windows.net/"  # The token URL for any Azure SQL database
connection_string = os.getenv("SQL_CONNECTION_STRING")
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
sql_engine = create_engine(connection_url)
azure_credentials = identity.DefaultAzureCredential()
@event.listens_for(sql_engine, "do_connect")

def provide_token(dialect, conn_rec, cargs, cparams):
    try:
        # remove the "Trusted_Connection" parameter that SQLAlchemy adds
        cargs[0] = cargs[0].replace(";Trusted_Connection=Yes", "")
        # create token credential
        raw_token = azure_credentials.get_token(TOKEN_URL).token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(raw_token)}s", len(raw_token), raw_token)
        # apply it to keyword arguments
        cparams["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: token_struct}
    except Exception as e:
        SQL_CONNECT_ERROR_MSG = "Microsoft Entra ID 身分驗證錯誤: %s", str(e)
        print(SQL_CONNECT_ERROR_MSG)   

def init():
    # 設定 streamlit 首頁
    st.set_page_config(
        page_title="Azure OpenAI Service ChatGPT 對話機器人",
        page_icon="🤖"
    )

def question_filter(input_str):
    try:
        prompt = PromptTemplate(input_variables=["prompt_str"],template="輸入:{prompt_str}\n" \
                                             "輸入的這句話的意圖是查詢嗎? 如果是並此問題可以在 Wikipedia 上查得到請回答一個字母 Y\n" \
                                             "輸入的這句話的意圖是查詢嗎? 如果是並此問題無法在 Wikipedia 上查得到請回答一個字母 N\n" \
                                             "如果輸入的這句話的意圖不是查詢，請回答一個字母 C\n")
        # 將 AzureChatOpenAI 以 LangChain 方式使用
        composed_chain =  prompt | chat | StrOutputParser()
        response = composed_chain.invoke (input_str)
    except Exception as e:
        print("發生錯誤: ", e)
        response = "發生了一點技術問題，我無法連線到 Azure OpenAI Service : %s", str(e)      
    return(response)

def get_query_english_keyword(input_str):
    try:
        prompt = PromptTemplate(input_variables=["prompt_str"],template="輸入:{prompt_str}\n" \
                                                "將輸入翻譯為一句包含關鍵字之英文\n" \
                                                )
        # 將 AzureChatOpenAI 以 LLMChain 方式使用
        composed_chain =  prompt | chat | StrOutputParser()
        response = composed_chain.invoke (input_str)        

    except Exception as e:
        print("發生錯誤: ", e)
        response = "發生了一點技術問題，我無法連線到 Azure OpenAI Service，請稍後再試: %s", str(e)
    return(response)

def embeddings_query(input_str):
    try:
        # 查詢文字轉換為 OpenAI Embeddings 向量值，再轉為 JSON 格式字串
        response = embeddings.embed_query(input_str)
        json_str = json.dumps(response)        
        # 查出最新相關的 3 個條目
        sql = "select top 3 cosine_distance,title,url from dbo.SimilarContentArticles ('"+ json_str + "') as r order by cosine_distance desc"
        # 查詢結果置於 DataFrame    
        with sql_engine.connect()  as conn:
            output_df = pd.read_sql_query(sa.text(sql), conn)               
    except Exception as e:        
        SQL_CONNECT_ERROR_MSG = "，錯誤訊息: %s", str(e)
        print(SQL_CONNECT_ERROR_MSG)
        # 錯誤代處理
        output_df = pd.DataFrame()
    return (output_df)

def answer_summary (input_str,title):
    try:
        # 取得 Simple English Wikipedia 的網頁內容
        docs = WikipediaLoader(query=title, load_max_docs=1).load()
        html_body = docs[0].page_content[:2000]    
        # 將網頁內容轉換為摘要
        prompt = PromptTemplate(input_variables=["question_str","html_str"],template="事實:{question_str}\n" \
                                                "HTML:{html_str}\n" \
                                                "解析 HTML 的內容，依據這些內容以一百字摘要的方式，用繁體中文回答事實內提出的問題，" \
                                                "如果 HTML 解析出來的內容無法回答事實內的問題，則回覆 '很抱歉我不知道答案，這是最接近的條目'" \
                                                "回覆:")

        # 將 AzureChatOpenAI 以 Lang Chain 方式使用
        composed_chain =  prompt | chat | StrOutputParser()
        response = composed_chain.invoke (input={"question_str":input_str,"html_str":html_body})        
    except Exception as e:
        print("發生錯誤: ", e)
        # 發生錯誤時的回覆
        response = "資料庫連線或是 Wikipedia 內容載入發生了一點技術問題，我無法正常查詢與回覆內容: %s", str(e)
    return (response)

def main():
    init()

    # 起始 messages session
    if "messages" not in st.session_state:
        st.session_state.messages = [
            SystemMessage(content='你是一個針對 Wikipeida 內容查詢的繁體中文的對話機器人，以活潑風格回問題')
        ]
        st.session_state.messages.append(AIMessage(content="您好。我是一個可以運用 OpenAI Embeddings 比對查詢 Simple English Wikipeida 的對話機器人。"))

    st.header("Azure OpenAI Service 打造之 🤖")

    # 處理側邊用戶輸入
    with st.sidebar:
        user_input = st.text_input("輸入訊息: ", key="user_input")

        # 處理用戶輸入
        if user_input: 
            st.session_state.messages.append(HumanMessage(content=user_input))
            with st.spinner("思考中..."):
                # 判斷用戶輸入內容類型
                question_type = question_filter(user_input)
                if question_type == 'Y': 
                    # 將用戶輸入文字轉換為英文，以增加查詢準確度
                    english_keyword = get_query_english_keyword(user_input) 
                    # 將英文轉換為 OpenAI Embeddings 向量值，再轉為 JSON 格式字串對 SQL Server 進行餘懸進行餘弦相似度計算比對                  
                    respons_str = '這是用 OpenAI 所提供的 Simple English Wikipeida Embeddings 資料，比對出來最相關的三個條目，\n'
                    respone_df = embeddings_query(english_keyword)
                    # 顯示向量近似查詢結果於左側窗格
                    st.markdown("比對內容: "+ english_keyword)
                    st.dataframe(respone_df)
                    
                    # 取得第一個條目的標題，做內容為回覆摘要
                    if (len(respone_df.index)>0):                        
                        respons_str = respons_str + answer_summary (english_keyword,respone_df.iloc[0]['title']) + "\n\n 資料來源: \n"
                        # 將最接近的三個條目的網址加入參考資料
                        for index, row in respone_df.iterrows():
                            respons_str = respons_str + str(index+1)+". [*" + row['title'] + "*](" +  row['url'] + ") \n"                        
                    else:
                       respons_str = "LangChain 的 Wikipedia Loader 載入內容時發生了一點技術問題，我無法彙整出摘要。"+SQL_CONNECT_ERROR_MSG
                    
                    st.session_state.messages.append(AIMessage(content=respons_str))
                else:
                    if question_type == 'C':
                        # 非查詢類問題，讓 ChatGPT 模型自由回答
                        prompt = PromptTemplate(input_variables=["prompt_str"],template="輸入:{prompt_str}\n")                        
                        composed_chain =  prompt | chat | StrOutputParser()
                        response = composed_chain.invoke (st.session_state.messages)                     
                        # 將回覆資料加入對話歷史紀錄 
                        st.session_state.messages.append(AIMessage(content=response))
                    else:
                        # 處理無法回覆之查詢問題 
                        st.session_state.messages.append(AIMessage(content="很抱歉，我不知道 ..."))
                
    # 顯示對話歷史紀錄
    messages = st.session_state.get('messages', [])
    for i, msg in enumerate(messages[1:]):
        if i % 2 == 0:  
            # 用戶輸入          
            with st.chat_message("user"):
                st.markdown(msg.content)
            
        else:            
            # 機器人回覆
            with st.chat_message("assistant"):
                st.markdown(msg.content)
         

if __name__ == '__main__':
    main()