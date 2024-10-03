###
#2022-03-11     作成　AraiKenji
#MANTANWEB記事ページ表示Lambda
#〜〜〜〜〜〜〜〜〜
#2023-03-20     新写真ページ(photopage)パンくず対応（【写真 1／10枚】xxx対応
#2023-04-04     反響・感想、あらすじ実装
#2023-04-10     関連記事のpolicyチェック追加
#2023-04-10     反響・感想、あらすじのSQLでstraight_joinをjoinに変更
#2023-04-13     ampのメイン画像を画素数max（最高size10.jpg）に対応
#2023-04-18     写真ページでのtitleタグ写真説明をtitleタグに入れる。ない場合は、【写真1／8】$記事title＄- MANTANWEB（まんたんウェブ）
#2023-04-29     SNS埋め込み用対応　CreateSNSembedDataHTML(f_i_data)追加
#2023-05-08     ジャンルアイドル対応（/matome/を
#2023-05-08     グラビア対応　テンプレート出し分け テンプレート選択前にPolicyCheckを実施して出し分ける
#2023-05-13     image_info[photo_num-1]['caption']がない場合の対応修正
#2023-06-06     グラビア、コスプレは、グラビアサイトへ301リダイレクト対応
#2023-07-04     台紙対応
#2023-07-12     関連記事サムネールなし対応
#2023-07-13     グラビア301本番系対応　＋旧写真ページURLでの301リダイレクト対応
#2023-07-18     関連記事のグラビアでのkeyvalue制御追加
#2023-07-18     ジャンル最新記事一覧から台紙を除外
#2023-07-26     リダイレクト時のext_m=パラメーター保持
#2023-08-02     外部配信用パラメータ付の場合でのcanonical対応
#2023-08-17.    まとめボックス追加
#2023-09-02     AMPのグラビアも301リダイレクト対応
#2023-09-05     アフィリエイトタグ実装対応
#2023-09-07     AffiliateTagCreate()に広告ラベルー広告ーの表示を追加
#2023-09-12     sns_only==1除外対応
#2023-12-20     メイン動画タグ対応

import json
import boto3
import pymysql.cursors
import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import os
import urllib.parse
import math
import random
import uuid
from urllib.parse import unquote_plus
from PIL import Image
import PIL.Image
import calendar

import ast

import config as CONF
import template as TEMP

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
sentry_sdk.init(
    dsn="https://ed74bf47b7264d09a8e655a7dba7f136@o1342284.ingest.sentry.io/6726664",
    integrations=[
        AwsLambdaIntegration(),
    ],

    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production,
    traces_sample_rate=1.0,
)

#S3
s3 = boto3.resource('s3')
s3cli = boto3.client('s3')

CONFIG_JSON = json.loads(s3.Object(CONF.config_file_bucket, CONF.config_file).get()['Body'].read().decode('utf-8'))

    
#APIGateWayからの受け取り
def lambda_handler(event, context):
    print(event)
    
    status_code="200"#レスポンスステータスコード　デフォルトは200をセット
    
    photo =""
    ext_m ="" #外部配信時のパラメーター（アフィリエイト制御対応）
    
    if event.get('queryStringParameters'):
        if event['queryStringParameters'].get('photo'):
            photo = event['queryStringParameters'].get('photo')
         
        ext_m = event['queryStringParameters'].get('ext_m')


    dt_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y/%m/%d %H:%M') # 日本時刻
    
    previewmode= ""

    #端末判別処理
    headers = event.get('headers')
    queryData = event.get('queryStringParameters')
    #Cloudfront-Is-Mobile-Viewer
    if CONFIG_JSON['mobile_user_agent'] in str(headers) and headers[CONFIG_JSON['mobile_user_agent']] == 'true':
        device = 'sp'
    elif "Cloudfront-Is-Mobile-Viewer" in str(headers) and headers["Cloudfront-Is-Mobile-Viewer"] == 'true':
        device = 'sp'
    else:
        device = 'pc'
        
    path = event['path']
    news_item_id =""
    
    TEMPLATE_PATH = CONF.template_path #デフォルトのテンプレートパス

    #301リダイレクト処理                                            #################################
    #古いタイプのURLはリダイレクトさせる　2023-01-30
    #例：https://mantan-web.jp/article. /なし
    #例：https://mantan-web.jp/photo/20140805dog00m200032000c.html?page=002
    #例：https://mantan-web.jp/gallery/2013/09/26/20130926dog00m200010000c/010.html
    if "/gallery/" in path or "/photo/" in path or path == '/article':
        temp_path_arry = path.split("/")
        conv_path =""
        query =""
        conv_path = path.replace("/photo/","/article/").replace("/gallery/","/article/")

        #記事一覧トップで/がない場合。
        if path == '/article':#https://mantan-web.jp/article
            conv_path = '/article/'

        elif len(temp_path_arry) ==7:
            conv_path = "/article/"+temp_path_arry[5] +".html"
            #photo=temp_path_arry[6].replace(".html","")
        elif len(temp_path_arry) ==8:#/ampの場合
            conv_path = temp_path_arry[1]+"/article/"+temp_path_arry[5] +".html"
        
        #Queryがあれば、追加
        if event['queryStringParameters']:
            if event['queryStringParameters'].get('page'):
                photo = event['queryStringParameters'].get('page')
                query = "?photo="+photo
            elif ext_m:
                if "?" in query:
                    query += "&ext_m="+ ext_m
                else:
                    query += "?ext_m="+ ext_m
                
        
        #2023-01-30 301でリダイレクト 
        return {
            "statusCode": "301",
            "headers": {"Location": "https://mantan-web.jp"+conv_path+query}
        }
        ####リダイレクト処理　ここまで############################################################
    

    #pathを配列化
    patharry = path.split("/")
    
    
    if '/test/' in path:
        test_name = patharry[2]
        path = path.replace("/test/","").replace(test_name,"")
        patharry = path.split("/")
        #print(f"patharry={patharry}")
        TEMPLATE_PATH = f"test/{test_name}/deploy_template/" #/test/のテンプレートパス
    

    htmldata =""
    photopage_flg =""#写真ページかどうか？
    
    #外部配信時のパラメータ付与
    if ext_m:
        query ="?ext_m="+ext_m
    else:
        query = ""


    if path =='/article/' :# 1.articleトップ
        print("1.articleトップページ")
        htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['genre_html'][device]).get()['Body'].read().decode('utf-8')
        htmldata = InsertHtmlData(htmldata,device)
        
        genre_ranking_html =TEMP.LOGLY_RANKING
        htmldata =htmldata.replace('{%genre_ranking%}',genre_ranking_html)
        htmldata =htmldata.replace('{%title_ジャンル名%}',"ニュース一覧")
    
        
        htmldata =htmldata.replace("{%keyvalue_tag%}",f"googletag.pubads().setTargeting('tag','article');")
        
    elif '/article/archive' in path:#記事アーカイブ
        path_arry = path.split('/')
        targetdate =''
        if path[-5:] == '.html'  and len(path_arry) == 4 :
            targetdate = path_arry[3].replace('.html','')
        else:
            #日付指定がなければ、今日
            targetdate = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y%m%d')
            
        if len(targetdate) == 8:#日時指定の文字数があっていれば。
            htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['archive_html'][device]).get()['Body'].read().decode('utf-8')
            htmldata = InsertArchiveHtmlData(htmldata,device,targetdate)        
        else:
            htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
            status_code ="404"

        htmldata =htmldata.replace("{%genre_ranking%}",TEMP.LOGLY_RANKING)

        #keyvalueセット
        htmldata =htmldata.replace("{%keyvalue_tag%}",f"googletag.pubads().setTargeting('tag','article');")

    elif len(patharry)>=2 and patharry[1] =='article' and '.html' in patharry[2]:   #記事詳細公開ページ
        print("#記事詳細公開ページ")

        news_item_id= patharry[2].replace('.html','')

        #グラビア振り分け 2023-06-06 ###########################################################################
        if GravureCheck(news_item_id) == True and photo == '':
            print("これはグラビアの記事ページですので301グラビア専用サイトにリダイレクトします。")
            return {
                "statusCode": "301",
                "headers": {"Location": f"{CONF.gravure_site_url}/article/"+news_item_id+".html" + query}
            }
        ########################################################################################################    

        #2023-02-28 ジャンルテーブルからジャンルを取得するように追加
        sql =f'select * from {CONF.contents_tbl} left join contents_genre_tbl on {CONF.contents_tbl}.news_item_id = contents_genre_tbl.news_item_id where sts="open" and baitai_id like "in.%" and {CONF.contents_tbl}.news_item_id ="{news_item_id}"'
        result = GetDBdata('mantanweb',sql)
        if result:
            info_json = json.loads(result[0]['info_json'])
            if info_json.get('image_info'):
                image_info = info_json.get('image_info')
            else:
                result[0]["exist_photo"] = 0
                
            if photo != '' and result[0]["exist_photo"] == 1:       # 2．写真ページ表示   photoのパラメーターがあり、写真ありの場合のみ
                print("# 2．写真ページ表示")
                photopage_flg ="photopage"
                photo = photo[:3]
                if int(photo) > len(image_info):
                    #print("写真枚数以上のphotoが指定されました。"+photo)
                    htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
                    status_code ="404"
                    
                    # 404にもheader,footer component を採用
                    header_parts_html  = s3.Object(CONF.parts_bucket, "components/" + device +"_header.html").get()['Body'].read().decode('utf-8')
                    footer_parts_html  = s3.Object(CONF.parts_bucket, "components/" + device +"_footer.html").get()['Body'].read().decode('utf-8')
                    htmldata = htmldata.replace("{%header%}", header_parts_html)
                    htmldata = htmldata.replace("{%header-top%}", "")
                    htmldata = htmldata.replace("{%footer%}", footer_parts_html)
                    
                    return {                                    #結果出力
                        "statusCode": status_code,
                        "headers": {"Content-Type": "text/html","charset":"UTF-8"},
                        "body": htmldata,
                    }

                else:#?photo=001は、/photopage/001.htmlにリダイレクトする
                    conv_path =f'/article/{result[0]["news_item_id"]}/photopage/{photo}.html'
                    #if event['queryStringParameters']:
                        #if event['queryStringParameters'].get('ext_m'):
                            # extquery = "?ext_m="+ event['queryStringParameters'].get('ext_m'):
                            # conv_path = conv_path + extquery
                    #2023-03-24 301でリダイレクト 
                    return {
                        "statusCode": "301",
                        "headers": {"Location": conv_path+ query}
                    }
                    ####リダイレクト処理　ここまで############################################################
            else:#通常の記事詳細表示処理   # ３．記事詳細ページ表示    
                print("# ３．記事詳細ページ表示"+str(result[0].get("genre")))
                
                policy_result = PolicyChk(news_item_id) 
                main_kensaku = GetMainKensakuword(info_json)
                
                if main_kensaku == "台紙" or result[0]['sns_only'] ==1:      #SNS用台紙の場合、テンプレート出し分け
                    #print(f"テンプレート=article_sns_only_html")
                    htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['article_sns_only_html'][device]).get()['Body'].read().decode('utf-8')  
                elif ext_m != "":
                    #print(f"テンプレート=article_mid_html")
                    htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['article_mid_html'][device]).get()['Body'].read().decode('utf-8')  
                elif policy_result["tag_k"] ==1: #PolicyCheckでテンプレート出し分け
                    htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['article_gravure_html'][device]).get()['Body'].read().decode('utf-8')  
                else:    
                    #print(f"テンプレート=article_html")
                    htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['article_html'][device]).get()['Body'].read().decode('utf-8')    
                    
                ### matomebox ###
                htmldata = htmldata.replace('{%matomebox%}', CreateMatomeBox(main_kensaku, news_item_id))
                ### matomebox end ###
                
                htmldata = htmldata.replace('{%hebirote%}', CreateHebiroteHtml())
                
                
                htmldata = AffiliateTagInsert(device,news_item_id,htmldata,ext_m)   

                ###############################################
                
                    
                htmldata = InsertPhotoAndPreNextData(device,htmldata,result[0],"open")
            

            htmldata = InsertArticleData(device,htmldata,result[0],"open",photopage_flg,int(photo) if photo else 0)
        else:
            htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
            status_code ="404"
                
    elif len(patharry)>=3 and patharry[1] =='preview' and patharry[2] =="article" and '.html' in patharry[3]:#記事詳細プレビューページ
        print("#記事詳細プレビューページ")
        news_item_id= patharry[3].replace('.html','')
        #2023-02-28 ジャンルテーブルからジャンルを取得するように追加
        sql =f'select * from {CONF.contents_tbl} left join contents_genre_tbl on {CONF.contents_tbl}.news_item_id = contents_genre_tbl.news_item_id where  baitai_id="in.mantan-web.jp" and {CONF.contents_tbl}.news_item_id ="{news_item_id}"'
        result = GetDBdata('mantanweb',sql)
        previewmode='<span style="background:RED;color:#fff;font-size: 12px;padding: 0.5em;">プレビューモードで表示</span>'
        if result:
            info_json = json.loads(result[0]['info_json'])

            if photo != '' and result[0]["exist_photo"] == 1:                         # 2．写真ページ表示はpahotpageにリダイレクト
                #photopage_flg ="photo"
                photo = photo[:3]
                conv_path =f'/article/{result[0]["news_item_id"]}/photopage/{photo}.html'

                #2023-03-24 301でリダイレクト 
                return {
                    "statusCode": "301",
                    "headers": {"Location": conv_path}
                }
            else:                                        # ３．記事詳細ページ表示プレビュー                            
                htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['article_html'][device]).get()['Body'].read().decode('utf-8')
                htmldata = InsertPhotoAndPreNextData(device,htmldata,result[0],"preview")
                
            main_kensaku = GetMainKensakuword(info_json)
            ### matomebox ###
            htmldata = htmldata.replace('{%matomebox%}', CreateMatomeBox(main_kensaku, news_item_id))
            ### matomebox end ###
            
            
            htmldata = AffiliateTagInsert(device,news_item_id,htmldata,ext_m)   

                
            htmldata = InsertArticleData(device,htmldata,result[0],"preview",photopage_flg,int(photo) if photo else 0)               

        else:#DBにデータがなければNotFoundページ
            htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
            status_code ="404"
            
    elif '/preview/article' not in event['path'] and '/photopage' in event['path']:#2023-03-13 追加　写真専用ページ新設対応 #######################################################
        sts='"open"'
        news_item_id= patharry[2]
            
        print("処理７　photopageページ"+news_item_id)

        if len(patharry)<5:
            redirect_path = f"/article/{news_item_id}/photopage/001.html"
            return {
                    "statusCode": "301",
                    "headers": {"Location": "https://mantan-web.jp"+redirect_path+query}
            }
        elif len(patharry)==5:
            if patharry[4]=="000.html":
                redirect_path = f"/article/{news_item_id}/photopage/001.html"
                return {
                        "statusCode": "301",
                        "headers": {"Location": "https://mantan-web.jp"+redirect_path + query}
                }                

        sql =f'select * from {CONF.contents_tbl} left join contents_genre_tbl on {CONF.contents_tbl}.news_item_id = contents_genre_tbl.news_item_id where sts={sts} and baitai_id like "in.%" and {CONF.contents_tbl}.news_item_id ="{news_item_id}"'
        result = GetDBdata('mantanweb',sql)
        if result:
            info_json = json.loads(result[0]['info_json'])
            if info_json.get('image_info'):
                image_info = info_json.get('image_info')
            else:
                result[0]["exist_photo"] = 0
                image_info =[]

            if patharry[4]:
                photo = patharry[4].replace(".html","")
                if int(photo) > len(image_info):
                    print("写真枚数以上のphotoが指定されました。"+photo)
                    htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
                    status_code ="404"
                    
                    # 404にもheader,footer component を採用
                    header_parts_html  = s3.Object(CONF.parts_bucket, "components/" + device +"_header.html").get()['Body'].read().decode('utf-8')
                    footer_parts_html  = s3.Object(CONF.parts_bucket, "components/" + device +"_footer.html").get()['Body'].read().decode('utf-8')
                    htmldata = htmldata.replace("{%header%}", header_parts_html)
                    htmldata = htmldata.replace("{%header-top%}", "")
                    htmldata = htmldata.replace("{%footer%}", footer_parts_html)
                    
                    return {                                    #結果出力
                        "statusCode": status_code,
                        "headers": {"Content-Type": "text/html","charset":"UTF-8"},
                        "body": htmldata,
                    }

                else:#通常の写真ページ表示処理#################################
                    #グラビア振り分け 2023-06-06 ###########################################################################
                    if GravureCheck(news_item_id) == True:
                        print("これはグラビアの写真ページですので301グラビア専用サイトにリダイレクトします。"+query)
                        return {
                            "statusCode": "301",
                            "headers": {"Location": f"{CONF.gravure_site_url}/article/{news_item_id}/photopage/{photo}.html{query}" }
                        }
                    ########################################################################################################    

                    #PolicyCheckでテンプレート出し分け
                    policy_result = PolicyChk(news_item_id) 
                    if policy_result["tag_k"] ==1:
                        #print("ポリシーチェック")
                        htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['photo_only_page_g_html'][device]).get()['Body'].read().decode('utf-8')               
                    else:
                        htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['photo_only_page_html'][device]).get()['Body'].read().decode('utf-8')
                        
                    #パラメーター付の場合のcanonical対応 2023-08-02 Arai
                    if ext_m !="":
                        htmldata = htmldata.replace("{%canonical%}",f'<link rel="canonical" href="https://mantan-web.jp/article/{news_item_id}/photopage/{photo}.html">')
                    else:
                        htmldata = htmldata.replace("{%canonical%}",'')
                        
                    ### matomebox ###
                    main_kensaku = GetMainKensakuword(info_json)
                    htmldata = htmldata.replace('{%matomebox%}', CreateMatomeBox(main_kensaku, news_item_id))
                    ### matomebox end ###
                        
                    htmldata = InsertPhotolistData(device,htmldata,result[0],photo,"open")#写真描画処理
                    htmldata = InsertArticleData(device,htmldata,result[0],"open","photopage",int(photo) if photo else 0)
                    
                    htmldata = htmldata.replace('{%hebirote%}', CreateHebiroteHtml())
                    ################################################################

            else:
                redirect_path = f"/article/{news_item_id}/photopage/001.html"
                return {
                    "statusCode": "301",
                    "headers": {"Location": "https://mantan-web.jp"+redirect_path + query}
                }
        else:
            htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
            status_code ="404"

            
    elif '/preview/article/' in event['path'] and '/photopage' in event['path'] :#2023-03-13 追加　写真専用ページ新設対応 #######################################################
        sts='"preview" or sts="wait" '
        news_item_id= patharry[3]
        photo = patharry[5].replace(".html","")
        print("処理8　photopageページプレビュー"+news_item_id)

        sql =f'select * from {CONF.contents_tbl} left join contents_genre_tbl on {CONF.contents_tbl}.news_item_id = contents_genre_tbl.news_item_id where sts={sts} and baitai_id like "in.%" and {CONF.contents_tbl}.news_item_id ="{news_item_id}"'
        result = GetDBdata('mantanweb',sql)
        if result:
            htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['photo_only_page_html'][device]).get()['Body'].read().decode('utf-8')
            htmldata = InsertPhotolistData(device,htmldata,result[0],photo,"open")#写真描画処理
            htmldata = InsertArticleData(device,htmldata,result[0],"open","photopage",int(photo) if photo else 0)

        else:#DBにデータがなければNotFoundページ
            htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
            status_code ="404"
    ##################################################################################################################################       
 
    elif '/amp/article/' in event['path'] :                             #　AMP　article
        print("処理６　AMPページ")    
        news_item_id = path.replace('/amp/article/','').replace('.html','')

        #2023-02-28 ジャンルテーブルからジャンルを取得するように追加
        sql =f'select * from {CONF.contents_tbl} left join contents_genre_tbl on {CONF.contents_tbl}.news_item_id = contents_genre_tbl.news_item_id where sts="open" and baitai_id like "in.%" and {CONF.contents_tbl}.news_item_id ="{news_item_id}"'
        result = GetDBdata("mantanweb",sql)
        if result:
            
            #グラビア振り分け 2023-09-02 ###########################################################################
            if GravureCheck(news_item_id) == True and photo == '':
                print("これはグラビアの記事ページですので301グラビア専用サイトにリダイレクトします。")
                return {
                    "statusCode": "301",
                    "headers": {"Location": f"{CONF.gravure_site_url}/amp/article/"+news_item_id+".html"}
                }
            ########################################################################################################    
            
            #PolicyCheckでテンプレート出し分け
            policy_result = PolicyChk(news_item_id) 
            if policy_result["tag_k"] ==1:
                #print("ポリシーチェック")
                htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['amp_article_gravure_html'][device]).get()['Body'].read().decode('utf-8')
            else:
                htmldata = s3.Object(CONF.template_bucket, TEMPLATE_PATH + CONFIG_JSON['Templates']['amp_article_html'][device]).get()['Body'].read().decode('utf-8')
                
            htmldata = InsertPhotoAndPreNextData("amp",htmldata,result[0],"open")
            htmldata = InsertArticleData("amp",htmldata,result[0],"open",photopage_flg,int(photo) if photo else 0)
 
        else:#DBにデータがなければNotFoundページ
            htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
            status_code ="404"
    
           
    else:
        htmldata = s3.Object(CONF.template_bucket, CONFIG_JSON['notfound_html'][device]).get()['Body'].read().decode('utf-8')
        status_code ="404"

    
    htmldata = PartsAssemble(htmldata,device)

    #PolicyCheck
    policy_result = PolicyChk(news_item_id) 
    if policy_result["tag_k"] ==1:
        if '/amp/article/' in event['path'] :
            htmldata =htmldata.replace("{%keyvalue_tag%}\n","json='{\"targeting\":{\"tag\":[\"gravure\"]}}'\n")
        else:
            htmldata =htmldata.replace("{%keyvalue_tag%}\n","googletag.pubads().setTargeting('tag','gravure');\n")
    else:
        htmldata =htmldata.replace("{%keyvalue_tag%}\n","")
        
    if policy_result["overlay"] !=0:
        startposi= htmldata.find(CONF.overlay_tag)
        endposi=htmldata[startposi:].find("</div>")
        cutstring = htmldata[startposi:startposi+endposi+6] 
        htmldata = htmldata.replace(cutstring,"")

        startposi= htmldata.find(CONF.pol_ctl_start)        
        endposi=htmldata[startposi:].find(CONF.pol_ctl_end)
        cutstring = htmldata[startposi:startposi+endposi+len(CONF.pol_ctl_end)+1] 
        htmldata = htmldata.replace(cutstring,"")       
        
    #プレビューモードの時に題字下に表示
    htmldata = htmldata.replace("{%OpenorPreview%}",previewmode)
    
    # 2023-11-22 headerとfooterの共通化
    header_parts_html  = s3.Object(CONF.parts_bucket, "components/" + device +"_header.html").get()['Body'].read().decode('utf-8')
    footer_parts_html  = s3.Object(CONF.parts_bucket, "components/" + device +"_footer.html").get()['Body'].read().decode('utf-8')
    htmldata = htmldata.replace("{%header%}", header_parts_html)
    htmldata = htmldata.replace("{%header-top%}", "")
    htmldata = htmldata.replace("{%footer%}", footer_parts_html)
                           
    return {                                    #結果出力
        "statusCode": status_code,
        "headers": {"Content-Type": "text/html","charset":"UTF-8"},
        "body": htmldata,
    }
    
#Access-Control-Allow-Origiの参考メモ
#return {
#    'statusCode': 200,
#    'headers': {
#        "headers": {"Content-Type": "text/html","charset":"UTF-8","Access-Control-Allow-Origin": "*"},
#    },
#    'body': json.dumps(edited_message)
#}

#・・・・・・・・サブ・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・・
def AffiliateTagInsert(device,news_item_id,htmldata,ext_m):#アフィリエイトタグ差込
    page_data = {}

    if ext_m =="y":

        page_data['アフィリエイトタグ_main'] = ""
        page_data['アフィリエイトタグ_sub']  = ""
        page_data['アフィリエイトタグ_sub_スマホ版']  = ""

    else:
        affiliate_tags = AffiliateTagCreate(news_item_id)
        

        page_data['アフィリエイトタグ_main'] = affiliate_tags["main_tag"]
        page_data['アフィリエイトタグ_sub']  = affiliate_tags["sub_tag"]
        if device =="sp":#アフィリエイトタグ_subのスマホ版での出し分け
            page_data['アフィリエイトタグ_sub_スマホ版']  = affiliate_tags["sub_tag"]
        else:
            page_data['アフィリエイトタグ_sub_スマホ版']  = ""
            
        
    #HTMLデータ一括差し替え
    for key, value in page_data.items():
        htmldata = htmldata.replace('{%' + key + '%}', value)
        
    return(htmldata)
    
    
def AffiliateTagCreate(news_item_id):
    main_tag =""
    sub_tag =""
    sql =f'select main_tag,sub_tag from affiliate_tbl where news_item_id="{news_item_id}"'
    result = GetDBdata("mantanweb",sql)
    if result:
        main_tag = result[0].get("main_tag")
        if main_tag:
            main_tag = TEMP.ad_label +main_tag

        sub_tag  = result[0].get("sub_tag")
        if sub_tag:
            sub_tag = TEMP.ad_label +sub_tag
        
    return{"main_tag":main_tag,"sub_tag":sub_tag}
    

#グラビア、コスプレチェック 2023-06-06
def GravureCheck(news_item_id):
    sql =f'select tag from contents_tag_tbl where news_item_id = "{news_item_id}"'  
    result = GetDBdata("mantanweb",sql)
    tag_arry = [r["tag"] for r in result] #タグ（tag）をリスト 
    for db_data in result:
        if db_data["tag"] =="グラビア" or  db_data["tag"] =="コスプレ":
            return(True)
    return

def PolicyChk(news_item_id):#DB テーブル＝policy_violation_tbl
    overlay=0
    tag_k=0
    sql = f'select * from policy_violation_tbl where news_item_id ="{news_item_id}";'
    result = GetDBdata('mantanweb',sql)
    if len(result) !=0:
        for data in result:
            if data.get("overlay"):
                overlay += data.get("overlay")
            if data.get("tag_k"):
                tag_k += data.get("tag_k")
            
    return {"overlay":overlay,"tag_k":tag_k}
    
#メイン検索タグ取得 ###########################################################
def GetMainKensakuword(info_json):
    matome_name =""
    if info_json.get('flexible_info'):
        for f_i_data in  info_json['flexible_info']:
            if 'article_ext_info' in f_i_data.get('use_name'):#number ="12"
                matome_name = f_i_data.get('value')['main_tag']


    return(matome_name)
    
# 記事種別取得
def GetArticleKind(info_json):
    kind = ""
    if info_json.get('flexible_info'):
        for f_i_data in  info_json['flexible_info']:
            if 'article_ext_info' in f_i_data.get('use_name'):#number ="12"
                kind = f_i_data.get('value')['kind']
    return kind
#################################################################################  

    
def InsertHtmlData(htmldata,device):#ニュース記事一覧/article/トップ
    sql = 'select * from '+CONF.contents_tbl+' where sts = "open" and baitai_id="in.mantan-web.jp" order by first_open_datetime desc limit 20;'
    result = GetDBdata('mantanweb',sql)
    article_list_html =''
    #記事リスト作成
    for ii,dbdata in enumerate(result):
        image_url = ImageUrlCreate(dbdata,0,"open")
        
        if dbdata['kanrenmidasi']:
            kanrenmidasi = str(dbdata['kanrenmidasi'])+'：'
        else:
            kanrenmidasi = ""
        title =    kanrenmidasi +dbdata['midasibun']
        if device =="sp" and len(title) >25:
            title = title[:25] + '...'
        title = EscapeStr(title)#文字エスケープ
        article_list_html += TEMP.archive_list[device].replace('{%記事見出し%}',title)
        article_list_html = article_list_html.replace('{%関連見出し%}',"")
        article_list_html = article_list_html.replace('{%image_url_small%}',image_url['image_url_small'])
        article_list_html = article_list_html.replace('{%image_url_mid%}',image_url['image_url_mid'])
        article_list_html = article_list_html.replace('{%image_url_micro%}',image_url['image_url_micro'])
        article_list_html = article_list_html.replace('{%first_open_datetime_dt%}',dbdata['first_open_datetime'].strftime('%Y-%m-%d'))
        article_list_html = article_list_html.replace('{%first_open_datetime_dsp%}',dbdata['first_open_datetime'].strftime('%Y年%m月%d日'))
        article_list_html = article_list_html.replace('{%記事url%}','/article/'+dbdata['news_item_id'] +'.html')
           
        info_json =  json.loads(dbdata['info_json'])
        if len(info_json['text'][0]) >90:
            article_list_html = article_list_html.replace('{%本文…%}',EscapeStr(info_json['text'][0][:90]+"..."))
        else:
            article_list_html = article_list_html.replace('{%本文…%}',EscapeStr(info_json['text'][0]))

        if info_json.get("image_info"):
            article_list_html = article_list_html.replace('{%写真枚数%}',str(len(info_json['image_info'])))
        else:
            article_list_html = article_list_html.replace('{%写真枚数%}',"0")

    page_data ={}
    
    page_data['genre'] ='article'
    page_data['ジャンル名'] ='ニュース一覧'
    page_data['ジャンルアーカイブurl'] ='/'+'article/archive/'
    
    page_data['kprw_list'] =""#共同通信PRワイヤー用のタグを空欄で削除

    page_data['カテゴリー記事リスト'] =article_list_html
    
    #HTMLデータ一括差し替え
    for key, value in page_data.items():
        htmldata = htmldata.replace('{%' + key + '%}', value)
        
    return htmldata

#記事アーカイブ日付指定
def InsertArchiveHtmlData(htmldata,device,targetdate):

    targetdatetime = datetime.datetime.strptime(targetdate, '%Y%m%d')
   
    sql = 'select * from '+CONF.contents_tbl+' where first_open_datetime BETWEEN '+targetdate+' and '+targetdate+'+ INTERVAL 1 DAY - INTERVAL 1 SECOND and sts = "open" and baitai_id="in.mantan-web.jp" order by first_open_datetime desc;'

    result =  GetDBdata('mantanweb',sql)
    htmldata = CreateArchiveHtml(htmldata,result,'article',targetdate,device)

    return htmldata
    
def CreateArchiveHtml(htmldata,articledata,genre,targetdate,device):  
    target_year  = targetdate[:4]
    target_month = targetdate[4:6]
    target_day = targetdate[6:8]
    htmldata = htmldata.replace('{%当該年月%}',target_year+'年'+target_month+'月'+target_day+'日')


    lists_html =''
    if len(articledata) ==0:
        lists_html += '<div class="no-article"><p>この日の記事はありません。</p></div>'
    else:
        for listdata in articledata:
            page_data ={}
            page_data['関連見出し'] =""

            
            if listdata["kanrenmidasi"]:
                kanrenmidasi = listdata["kanrenmidasi"]+"："
            else:
                kanrenmidasi = ""
                
            title = kanrenmidasi + listdata["midasibun"]
            
            if device =="sp" and len(title)>25:
                page_data['記事見出し'] = EscapeStr(title[:25]+'...')
            else:
                page_data['記事見出し'] = EscapeStr(title)
            page_data['記事url'] = '/article/'+ listdata['news_item_id'] +'.html'
            page_data['news_item_id'] = listdata['news_item_id']
            page_data['first_open_datetime_dt'] = listdata['first_open_datetime'].strftime('%Y-%m-%d')
            page_data['first_open_datetime_dsp'] = listdata['first_open_datetime'].strftime('%Y年%m月%d日')
            image_url = ImageUrlCreate(listdata,0,"open")#画像のbaseurlを返す
            page_data['image_url_small'] = image_url['image_url_small']
            page_data['image_url_mid'] = image_url['image_url_mid']
            page_data['image_url_micro'] = image_url['image_url_micro']
            info_json =  json.loads(listdata['info_json'])

            if GetMainKensakuword(info_json) =="台紙" or listdata['sns_only'] == 1:
                #print("台紙なので除外")
                continue
            
            kind = GetArticleKind(info_json)
            page_data['記事種別'] = '' if kind == '' else f'<span>{kind}</span> '
            
            if len(info_json['text'][0]) >90:
                page_data['本文…'] =EscapeStr(info_json['text'][0][:90]+"...")
            else:
                page_data['本文…'] =EscapeStr(info_json['text'][0])

            
            if info_json.get("image_info"):
                page_data['写真枚数'] = str(len(info_json['image_info']))
            else:
                page_data['写真枚数'] ="0"

                              
            html_str = TEMP.archive_list[device]
            for key, value in page_data.items():
                html_str = html_str.replace('{%' + key + '%}', value)    
            lists_html += html_str +'\n'
        
    #pager
    year_option =''
    month_option =''
    start_year =2012
    start_yearmonth = str(start_year) +'07'
    start_yearmonthday = str(start_yearmonth) +'05'
    this_year = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y') # 日本現在年月
    this_yearmonth = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y%m') # 日本現在年月
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y%m%d') # 本日
    #年のプロダウンメニュー作成
    for ii in range(int(this_year) + 1 - start_year) :
        if int(target_year) == start_year+ii:
            year_option  +=  '<option value="'+str(start_year+ii)+'" selected="selected">'+str(start_year+ii)+'</option>'
        else:
            year_option  +=  '<option value="'+str(start_year+ii)+'">'+str(start_year+ii)+'</option>'
    #月のプルダウンメニュー作成        
    for ii in range(12):
        if int(target_month) == ii+1:
            month_option  +=  '<option value="'+str(ii+1)+'" selected="selected">'+str(ii+1)+'</option>'
        else:
            month_option  +=  '<option value="'+str(ii+1)+'">'+str(ii+1)+'</option>'
    targetyearmonth =  target_year+target_month
    dt_targetdate = datetime.datetime.strptime(targetdate, '%Y%m%d')    
    next_yearmonthdate = (dt_targetdate + relativedelta(days=1)).strftime('%Y%m%d')
    prev_yearmonthdate = (dt_targetdate - relativedelta(days=1)).strftime('%Y%m%d')
    
    
    next_day = (dt_targetdate + relativedelta(days=1)).strftime('%Y%m%d')#次の日
    prev_day = (dt_targetdate - relativedelta(days=1)).strftime('%Y%m%d')#前の日
    next_month = (dt_targetdate + relativedelta(months=1)).strftime('%Y%m01')#次の月
    prev_month = (dt_targetdate - relativedelta(months=1)).strftime('%Y%m01')#前の月
    
    page_data ={}
    if targetdate == start_yearmonthday:
        page_data['prev_day_html']=''
        page_data['left_archive_link_html']=''
    else:
        page_data['prev_day_html']=f'<a href="/{genre}/archive/{prev_day}.html" class="article-pager__prev">前の日</a>'
        page_data['left_archive_link_html']=f'<a href="/{genre}/archive/{prev_month}.html"><img src="/assets/images/icon_left_active.svg"></a>'
        
    if targetdate == today:
        page_data['next_day_html']=''
        page_data['right_archive_link_html']=''
    elif target_year+ target_month == this_yearmonth:
        page_data['next_day_html']=f'<a href="/{genre}/archive/{next_day}.html" class="article-pager__prev">次の日</a>'
        page_data['right_archive_link_html']=''
    else:
        page_data['next_day_html']=f'<a href="/{genre}/archive/{next_day}.html" class="article-pager__prev">次の日</a>'
        page_data['right_archive_link_html']=f'<a href="/{genre}/archive/{next_month}.html"><img src="/assets/images/icon_right_active.svg"></a>'
       
    page_data['ジャンル記事リスト']=lists_html
    page_data['year_option_html']=year_option
    page_data['month_option_html']=month_option
    page_data['genre'] = genre
    page_data['ジャンルアーカイブurl'] = '/'+genre+'/archive/'
    page_data['ジャンル名'] = 'ニュース一覧'
    page_data['当該年']=target_year
    page_data['当該月']=target_month
    page_data['当該年月日']=f'{target_year}年{target_month}月{target_day}日'
    page_data['search_day'] = target_day
    page_data['cal_select_day'] = CreateCalendar(target_year,target_month,target_day,genre)#日付指定のカレンダー
    
    page_data['no_data']=""

    #HTMLデータ一括差し替え
    for key, value in page_data.items():
        htmldata = htmldata.replace('{%' + key + '%}', value)
 
            
    return(htmldata)
  
   
#カレンダー作成 未来にはリンクなしバージョン
def CreateCalendar(year,month,day,genre):
    cal_html = '<tr><td style="color:red;">日</td><td style="color:blue;">月</td><td style="color:blue;">火</td><td style="color:blue;">水</td><td style="color:blue;">木</td><td style="color:blue;">金</td><td style="color:blue;">土</td></tr>'
    calendar.setfirstweekday(calendar.SUNDAY)
    cal_data =calendar.monthcalendar(int(year),int(month))
    this_year = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y') 
    this_month = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%m')
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%d') # 日本現在年月

    for week in cal_data:
        cal_html += '<tr>'
        for d in week:
            if d ==0:
                cal_html += '<td></td>'
            elif d == int(day):
                cal_html += f'<td class="cr"><a href="/{genre}/archive/{year}{month}{str(d).zfill(2)}.html">{d}</a></td>'
            elif this_year == year and this_month ==month and d >int(today):
                cal_html += f'<td>{d}</td>'
            else:
                cal_html += f'<td><a href="/{genre}/archive/{year}{month}{str(d).zfill(2)}.html">{d}</a></td>'
                
        cal_html += '</tr>'
        
    return cal_html
     
   
   
   
#photoページ用　写真描画処理
def InsertPhotolistData(device,htmldata,article_data,photo,OpenorPrev):
    print(f"InsertPhotolistData {photo}")
    photo_num = int(photo)-1
    page_data = {}
    info_json = json.loads(article_data['info_json'])
    image_info = info_json.get('image_info')

    news_item_id = article_data['news_item_id']
    article_date_disp = article_data['first_open_datetime'].strftime('%Y年%m月%d日 %H:%M')
    article_date_datetime = str(article_data['first_open_datetime'])
    article_update_datetime = str(article_data['updatestamp'])
    
    #画像系処理
    image_url = ImageUrlCreate(article_data,photo_num,OpenorPrev)    
    page_data['記事写真'] = image_url['image_url_mid']
    image_size = GetImageSize(CONF.image_bucket,image_url['mid_path'])
    page_data['orig_photo_width'] =str(image_size['width'])
    page_data['orig_photo_height'] =str(image_size['height'])
    
    preview_url =""
    if OpenorPrev =="preview":
        preview_url ="/preview"    
    page_data['写真ページurl'] =preview_url+'/article/'+news_item_id+'.html?photo='+photo
    

    #image_jsonを生成する。
    image_json_arry = []        
    #image_list_html = '' #2023-03-18コメントアウト
    photo_sum_all = len(image_info)
    
    
    page_data['全写真枚数'] = str(photo_sum_all)
    
    #2023-04-18 写真ページでのtitleタグ
    if article_data.get('kanrenmidasi'):
        kanrenmidashi = article_data.get('kanrenmidasi') +"："
    else:
        kanrenmidashi =  ""
    

    photo_title=""
    if image_info[int(photo)-1]['caption']:
        caption_len = len(image_info[int(photo)-1]['caption'])
    else:
        caption_len =0
        
    if image_info[int(photo)-1]['caption'] == "": #写真説明がない場合
        photo_title = kanrenmidashi + article_data.get('midasibun')

    elif caption_len ==0:
        photo_title = kanrenmidashi + article_data.get('midasibun')
        
    elif caption_len <12:  #写真説明が12文字未満であれば
        photo_title = image_info[int(photo)-1]['caption'] + " "+ kanrenmidashi + article_data.get('midasibun')
    else:                                               #写真説明が12文字以上あれば
        photo_title = image_info[int(photo)-1]['caption']
        
    #写真ページのtitleタグ
    if photo_sum_all==1:
        page_data['title写真'] = f"【写真】" +photo_title
    else:
        page_data['title写真'] = f"【写真 {int(photo)}/{photo_sum_all}枚】" +photo_title
        
      


    for ii,image_data in enumerate(image_info):

        image_url = ImageUrlCreate(article_data,ii,OpenorPrev)

        image_base_url =CONFIG_JSON['image_storage_urls'][OpenorPrev]  + image_data['path']+'/'+image_data['filename']['basename']
        photonum = ('000' + str(ii) )[-3:]

        image_url_str =image_url['image_url_mid'] if device == "sp" else image_url['image_url_orig']#deviceで解像度を振り分ける2022-11-15 2023-04-18 orig=>mid最高size9へ

        #__image(image_json)に全写真のデータを入れていく
        if image_info[ii]['caption']:
            caption = image_info[ii]['caption']
        else:
            caption =""

        jsondata = {"src":image_url_str,"caption":caption}
        
        if ii == int(photo)-1:#実画像表示 2023-03-14
            next_num = int(photo)+1 if  int(photo)+1 <=photo_sum_all else 1
            prev_num = int(photo)-1 if  int(photo)-1 >0 else 1
            htmldata =htmldata.replace("{%image_src_url%}",image_url_str)
            if image_info[ii]['caption']:
                htmldata =htmldata.replace("{%写真説明%}",image_info[ii]['caption'])
            else:
                htmldata =htmldata.replace("{%写真説明%}","")
            htmldata =htmldata.replace("{%次の写真のURL%}",f'/article/{news_item_id}/photopage/{("000" + str(next_num) )[-3:]}.html')
            htmldata =htmldata.replace("{%前の写真のURL%}",f'/article/{news_item_id}/photopage/{("000" + str(prev_num) )[-3:]}.html')
            
        image_json_arry.append(jsondata) 
        srcurl = preview_url+'/article/'+ news_item_id +'.html?photo='+photonum
        
        if "prm" in news_item_id:
            imgurl = image_base_url +'_size5.'+image_data['filename']['ext']
        else:
            imgurl = image_base_url +'_thumb.'+image_data['filename']['ext']
            

    page_data['images_json'] = json.dumps(image_json_arry).replace("'","\\'")#シングルクォーテーションのエスケープ処理
    page_data['選択数'] = str(int(photo))
    

    #page_data['写真リストデータ'] = image_list_html #2023-03-15コメントアウト
   
    #HTMLデータ一括差し替え
    for key, value in page_data.items():
        htmldata = htmldata.replace('{%' + key + '%}', value) 
    
    return htmldata

    
#記事詳細ページ用.    写真と前後記事リンク付与  （画像と前後記事リスト）  
def InsertPhotoAndPreNextData(device,htmldata,article_data,OpenorPreview):
    if article_data['info_json']:
        print("info_jso あり。記事詳細ページ用写真と前後記事リンク付与  （画像と前後記事リスト）")
    
    else:           #info_jsonがまだできていない
        print("info_jso が空")
        return(htmldata)   
    
    page_data = {}
    

    info_json = json.loads(article_data['info_json'])
    image_info = info_json.get('image_info')
    news_item_id = article_data['news_item_id']
    
    keywords =""
    if info_json.get("flexible_info"):
        for f_i in info_json.get("flexible_info"):
            if f_i.get("number") == "4" or  f_i.get("use_name") =="キーワード":
                keywords= f_i.get("value")


    if 'datetime' in str(type(article_data['first_open_datetime'])):
        article_date_disp = article_data['first_open_datetime'].strftime('%Y年%m月%d日 %H:%M')
    else:
        article_date_disp = ""


    try:
        article_date_datetime = article_data['first_open_datetime'].strftime('%Y-%m-%d')
    except Exception as e:
        article_date_datetime =""
        print(f"エラー{e}")
    article_update_datetime = str(article_data['updatestamp'])
    
    
    #記事前後リンク生成
    #print("記事前後リンク生成")
    next_id=""
    hitNum=0
    first_open_datetime = article_data["first_open_datetime"]
    baitai_id = article_data["baitai_id"]

    sql= f'select * from {CONF.contents_tbl} where first_open_datetime >= "{first_open_datetime}" and sts = "open" and baitai_id="{baitai_id}" order by first_open_datetime asc  limit 10;'
    result = GetDBdata('mantanweb',sql) 
    
    if device == "sp":
        moji_limit =31
    else:
        moji_limit =39
                

    if result:
        for ii,data in enumerate(result):
            if news_item_id == data["news_item_id"]:
                #台紙（snsのみ埋め込みページ）除外処理
                if len(result) >ii+1:
                    m_name = GetMainKensakuword(json.loads(result[ii+1]['info_json']))
                    if m_name=="台紙" or result[ii+1]['sns_only'] ==1:
                        hitNum = ii+2
                        break
                    else:
                        hitNum = ii+1
                        break 
                    break 
            
        if hitNum >=len(result):
            hitNum =len(result)-1
            page_data['前記事リンク']=''
            
        else:
            if result[hitNum]['kanrenmidasi']:
                kanrenmidasi = result[hitNum]['kanrenmidasi'] +"："
            else:
                kanrenmidasi =""
                
            prevtitle =kanrenmidasi+result[hitNum]['midasibun']
            if len(prevtitle) >moji_limit:
                prevtitle = prevtitle[:moji_limit]+ "…"
            
            page_data['前記事リンク']='<a href="/article/' +result[hitNum]['news_item_id'] +'.html" class="post-prev">'+prevtitle + '</a>'
            next_id = result[hitNum]['news_item_id'] 
        
    else:
        page_data['前記事リンク']=''
        
        
    hitNum=0
    sql= f'select * from {CONF.contents_tbl} where first_open_datetime <= "{first_open_datetime}" and sts = "open" and baitai_id="{baitai_id}" order by first_open_datetime desc,news_item_id desc limit 10;'
    result = GetDBdata('mantanweb',sql)    
    if result:
        for ii,data in enumerate(result):
            if news_item_id == data["news_item_id"]:
                #台紙（snsのみ埋め込みページ）除外処理
                if len(result) >ii+1:
                    m_name = GetMainKensakuword(json.loads(result[ii+1]['info_json']))
                    if m_name=="台紙" or result[ii+1]['sns_only'] ==1:
                        hitNum = ii+2
                        break
                    else:
                        hitNum = ii+1
                        break 
            
        if hitNum >=len(result):
            hitNum =len(result)-1 
            page_data['後記事リンク']=''

        else:   
            if result[hitNum]['kanrenmidasi']:
                kanrenmidasi = result[hitNum]['kanrenmidasi'] +"："
            else:
                kanrenmidasi =""
            
            nexttitle =kanrenmidasi+result[hitNum]['midasibun']
            if len(nexttitle) >moji_limit:
                nexttitle = nexttitle[:moji_limit]+ "…"
            
            page_data['後記事リンク']='<a href="/article/' +result[hitNum]['news_item_id'] +'.html" class="post-next">'+nexttitle+'</a>'
        
    else:
        page_data['後記事リンク']=''
               
    #画像系処理
    #print("後記事リンク生成完了")

    if article_data["exist_photo"] == 1 and image_info: #写真あり
        
        image_url = ImageUrlCreate(article_data,0,OpenorPreview)
        if device =="sp":#device毎に解像度を振り分け 2022-11-15
            figure_html = TEMP.figure_html[device].replace('{%写真url%}',image_url['image_url_mid'])#orig からmidに戻する　
        elif device =="amp":
            figure_html = TEMP.figure_html[device].replace('{%写真url%}',image_url['image_url_orig'])#2023-04-13 ampのみimage_url_origにする。origは最高size10
        else:
            figure_html = TEMP.figure_html[device].replace('{%写真url%}',image_url['image_url_mid'])#2023-04-18 midは最高size9

        #figure_html = TEMP.figure_html[device].replace('{%写真url%}',image_url['image_url_mid'])#orig からmidに戻する　
        #srcset対応 
        figure_html = figure_html.replace('{%data_srcset%}','data-srcset="'+image_url['image_url_mid']+' 1x, '+image_url['image_url_orig']+' 2x"')


        #script type="application/ld+json"用データ埋め込み
        image_size = GetImageSize(CONF.image_bucket,image_url['mid_path'])

        image_json_item_html = TEMP.image_json_item
        image_json_item_html = image_json_item_html.replace("{%記事写真%}",image_url['image_url_mid'])
        image_json_item_html = image_json_item_html.replace("{%orig_photo_width%}",str(image_size['width']))
        image_json_item_html = image_json_item_html.replace("{%orig_photo_height%}",str(image_size['height']))
        
        page_data['image_json_item'] =image_json_item_html
        
        #######　Twitterなどog:image、twitter:image用 sns.jpgがあれば、それを使用する 　####################
        sns_image_prefix = "storage"+image_info[0]['path']+'/'+image_info[0]['filename']['basename'] + "_sns.jpg"
        sns_image_url = CONFIG_JSON['image_storage_urls'][OpenorPreview] + image_info[0]['path']+'/'+image_info[0]['filename']['basename'] + "_sns.jpg"
        filelist = s3cli.list_objects(Bucket="mantan-web.jp", Prefix=sns_image_prefix) #sns用の画像がS3にあるかどうかチェック

        if "Contents" in filelist:

            page_data['og写真url'] =sns_image_url
        else:
            page_data['og写真url'] =image_url['image_url_mid']

        ###################################################################################################

        preview_url =""
        if OpenorPreview =="preview":
            preview_url ="/preview"

        photopage_url =preview_url+'/article/'+news_item_id+'.html?photo=001'
        figure_html = figure_html.replace('{%写真ページurl%}',photopage_url)
        page_data['写真url'] = f'{preview_url}/article/{news_item_id}/photopage/001.html'

        figure_html = figure_html.replace('{%画像ソースurl%}',image_url['image_url_mid'])
        page_data['画像ソースurl'] = image_url['image_url_mid']
        
        figure_html = figure_html.replace('{%photo__photo_width_height%}','width="'+str(image_size['width'])+'px" height="'+ str(image_size['height'])+'px"')
        
        if image_info[0].get('caption'):
            figure_html = figure_html.replace('{%altキャプション%}',EscapeStr(image_info[0]['caption']))#altはエスケープ処理
            figure_html = figure_html.replace('{%キャプション%}',image_info[0]['caption'])#記事詳細ページのキャプションはエスケープしない
            page_data['altキャプション'] = EscapeStr(image_info[0]['caption'])
            page_data['キャプション'] = image_info[0]['caption']
        else:
            figure_html = figure_html.replace('{%altキャプション%}',"")
            figure_html = figure_html.replace('{%キャプション%}',"")
            page_data['altキャプション'] = ""
            page_data['キャプション'] = ""
    
        
        total_photo_num = len(image_info)
        page_data['全写真枚数'] = str(total_photo_num)
        figure_html = figure_html.replace('{%全写真枚数%}',str(total_photo_num))
                
        image_list_html = ''
        
        if total_photo_num==1:#写真が１枚の時は表示しない
            page_data['写真を見る'] =""

        else:
            page_data['写真を見る'] =f'	<div class="article__photo-more"><a href="{photopage_url}" class="btn__photolist">写真を見る<span class="btn__photolist-count">全 {total_photo_num} 枚</span></a></div>'
            if device =='pc':
                photo_col = 4
            else:
                photo_col = 3
                

            if CONF.test_mode !="test":
                #2023-04-15 写真全部掲出する場合は、この2行if分をコメントアウト 
                if total_photo_num >photo_col:
                    total_photo_num = photo_col
            #############################################################
                
            image_list_html ='<div class="article__photolist">'
            for ii in range(total_photo_num):
                image_url = ImageUrlCreate(article_data,ii,OpenorPreview)

                if device == 'pc':
                    #image_path = CONFIG_JSON['image_storage_urls'][OpenorPreview]  + image_info[ii]['path']
                    filename = image_url['image_url_mid']
                    #image_list_html += '<a href="'+preview_url+'/article/'+ news_item_id +'.html?photo='+image_info[ii]['filename']['basename']+ '">'
                    image_list_html += '<a href="'+preview_url+'/article/'+ news_item_id +'/photopage/'+image_info[ii]['filename']['basename']+ '.html">'
                    image_list_html += f'<img src="{filename}" alt="" width="165" height="165"></a> '
                    
                   
                elif device =='amp':
                    filename = image_url['image_url_thumb2']
                    image_list_html += '<a href="'+preview_url+'/article/'+ news_item_id +'.html?photo='+image_info[ii]['filename']['basename']+ '">'
                    image_list_html += f'<amp-img src="{filename}" alt="" width="60" height="60" layout="fill"></a> ' 
                    
                else:
                    filename = image_url['image_url_thumb2']
                    image_list_html += '<a href="'+preview_url+'/article/'+ news_item_id +'.html?photo='+image_info[ii]['filename']['basename']+ '">'
                    image_list_html += f'<img src="{filename}" data-src="{filename}" alt=""  width="60" height="60" class="lazyload"></a>\n'
                    
            image_list_html+="</div>"
     
        page_data['写真リスト'] = image_list_html
        page_data['写真コンテンツ'] = figure_html
        page_data['写真ページurl'] = photopage_url

    else:
        page_data['写真コンテンツ'] = ""
        page_data['写真リスト'] = "" 
        page_data['写真を見る'] =""
        page_data['image_json_item'] =""

    #HTMLデータ一括差し替え
    for key, value in page_data.items():
        htmldata = htmldata.replace('{%' + key + '%}', value)
        
        
    #プレミアムバンダイTag付与
    htmldata=BandaiTage(htmldata,keywords)

    
    return htmldata
    
#######################記事詳細ページ作成. photoページ含む##############################################################
def InsertArticleData(device,htmldata,article_data,OpenorPreview,photopage_flg,photo_num):#DBデータからHTMLテンプレートにデータを挿入する処理（共通）
    page_data = {}
    if article_data['info_json']:
        print("InsertArticleData() start")
    else:           #info_jsonがまだできていない
        return(htmldata)

    info_json = json.loads(article_data['info_json'])
    
    image_info =[]#画像なしの時のために、image_infoの配列を初期化
    
    
    if info_json.get('image_info'):
        image_info = info_json.get('image_info')
        photo_all_sum = len(image_info)
    else:
        photo_all_sum =0

    news_item_id = article_data['news_item_id']

    if 'datetime' in str(type(article_data['first_open_datetime'])):
        page_data['article_date_disp'] = article_data['first_open_datetime'].strftime('%Y年%m月%d日 %H:%M')
        page_data['firstcreate_datetime'] = article_data['first_open_datetime'].strftime('%Y/%m/%d %H:%M:00')
        page_data['article_date_datetime'] = article_data['first_open_datetime'].strftime('%Y-%m-%d')
    else:
        page_data['article_date_disp'] =""
        page_data['firstcreate_datetime'] = ""
        page_data['article_date_datetime'] = ""
        
    page_data['article_update_datetime'] = str(article_data['updatestamp'])
    page_data['記事url'] = '/article/'+news_item_id +'.html'
    page_data['news_item_id'] = news_item_id
    page_data['AMPURL'] = '/amp/article/'+news_item_id +'.html'

    #関連見出し＋見出し文################################################################
    if article_data['kanrenmidasi']:
        kanren_kijimidasi = article_data['kanrenmidasi']+"："+article_data['midasibun']
    else:
        kanren_kijimidasi = article_data['midasibun']
        
    karen_kijimidasi_all = kanren_kijimidasi#関連見出し：見出し文の全文 パンくず用
    

    if len(kanren_kijimidasi) >25:
        kanren_kijimidasi = kanren_kijimidasi[:25]+"..."

    page_data['関連見出し記事見出し'] = kanren_kijimidasi
    
    if article_data['kanrenmidasi']:
        page_data['関連見出し'] = article_data['kanrenmidasi']+"："
    else:
        page_data['関連見出し'] =""
    page_data['Escapte記事見出し'] = EscapeStr(article_data['midasibun'])
    page_data['記事見出し'] = article_data['midasibun']
        
    
#    if photopage_flg =="photo" or photopage_flg =="photopage":
    if photopage_flg =="photopage":
        page_data['title'] =""
    else:
        page_data['title'] = EscapeStr(page_data['関連見出し'] +page_data['記事見出し'])
        #変更タイトルがflexible_infoにあったらそれを記事見出しにする
        if info_json.get("flexible_info"):
            for f_i in info_json.get("flexible_info"):
                if f_i.get("number") == "11" or  f_i.get("use_name") =="タイトル変更":
                    page_data['title'] = EscapeStr(f_i.get("value"))
    ########################################################################################

    #共同通信PRWの場合は、noindex対応
    if "prm" in news_item_id:
        page_data['noindex'] ='<meta name="robots" content="noindex">'
    else:
        page_data['noindex'] =""
    
    #タグ取得. ######################################################################
    tags_arry =[]
    sql = f'select * from contents_tag_tbl where news_item_id ="{news_item_id}";'
    result = GetDBdata("mantanweb",sql)
    tags_arry.extend([r["tag"] for r in result]) #タグをリスト内包表記で追加
    tags_arry = sorted(tags_arry, reverse=True)
    tmp_tags_arry = sorted(tags_arry, reverse=True)

    #本文中リンク付与用のtag(temp_tag)を作成
    for kk,temp_tag in enumerate(tmp_tags_arry):#本文中のリンク用にtemp_tagを作成
        for tag in tags_arry:
            if tag.find(temp_tag) != -1 and tag != temp_tag:
                #tmp_tags_arry.pop(kk)
                tmp_tags_arry[kk]="********"
                break
    #################################################################################
    
    
    #本文中　中見出しと画像挿入処理　４パラした広告制御###################################
    page_data['記事本文1パラ目']=""
    page_data['記事本文2パラ目']=""
    page_data['記事本文3パラ目']=""
    page_data['記事本文4パラ目']=""
    page_data['記事本文5パラ目以降']=""
    
    naka_photo = 1 #2番目の写真
    para_count = 1 #パラグラフカウント
    gattai_flg=0
    for ii,para in enumerate(info_json['text']):
        para = para.replace("\n","<BR>")
        if para =="":
            continue
        
        #本文中へのキーワードリンク　まとめページへのリンク 2023-01-25実装
        for kk,tag in enumerate(tmp_tags_arry):
            if para.find(tag) != -1 and tag !="":
                para = para.replace(tag,f'<a href="/matome/{tag}/">{tag}</a>',1)
                tmp_tags_arry[kk] =""

        if '　◇' in para[:2]:
            para_html = f'<h2 class="article__nakamidashi">{para}</h2>'
            
            if naka_photo+1 <= len(image_info):
                if image_info[naka_photo]['use_news'] == True:
                    image_url = ImageUrlCreate(article_data,naka_photo,OpenorPreview)#n枚目の画像の情報
                    image_size = GetImageSize(CONF.image_bucket,image_url['small_path'])
                    if device == "amp":                        
                        para_html += '<div class="article__thumb">'
                        para_html += f'<a href="/article/{news_item_id}.html?photo=00{naka_photo+1}" class="article__thumb_unit">'
                        width = int(image_size["width"]/2)
                        height= int(image_size["height"]/2)
                        para_html += f'<amp-img src="{image_url["image_url_small"]}" width="{width}px" height="{height}px" layout="intrinsic">'
                        para_html += f'</amp-img></a></div>'
                    else:
                        width = int(image_size["width"]/2)
                        height= int(image_size["height"]/2)
                        para_html += '<div class="article__thumb">'
                        para_html += f'<a href="/article/{news_item_id}.html?photo=00{naka_photo+1}" class="article__thumb_unit">'
                        para_html += f'<img src="{image_url["image_url_small"]}" data-src="{image_url["image_url_small"]}" width="{width}px" height="{height}px" class=" lazyload"></a></div>'
                naka_photo += 1
                
            gattai_flg =1
            
        elif '　－－' == para[:3]:
            para_html='<h3 class="article__question">'
            para_html+= f'{para}</h3>'
            gattai_flg =1

        else:
            para_html= f'<p class="article__text">{para}</p>'
            gattai_flg =0

            
        if para_count<=4 :
            page_data[f'記事本文{para_count}パラ目'] += para_html
            if gattai_flg == 0:
                para_count +=1
                para_html=""
                
        else:
            page_data["記事本文5パラ目以降"] += para_html + "\n"
            if gattai_flg ==0:
                para_count +=1
                
    #7パラ未満だった場合は、４パラ下広告は削除
    if para_count <=7:
        #print("7パラ未満なので４パラした広告削除")
        startposi= htmldata.find(CONF.ad_4_7tag_satart)        
        endposi=htmldata[startposi:].find(CONF.ad_4_7tag_end)
        cutstring = htmldata[startposi:startposi+endposi+len(CONF.ad_4_7tag_satart)+1] 
        htmldata = htmldata.replace(cutstring,"") 
    else:
        print("7パラ以上なので４パラした広告そのまま")
            
    #########################################################################       
    if article_data['baitai_id'] =="in.prw.mantan-web.jp":#共同通信PRワイヤーの処理
        info_json['text'][0] = info_json['text'][0].replace('<a href="','').replace('</a>','').replace('"','')
        cut_str="target="
        startposi= info_json['text'][0].find(cut_str)    
        info_json['text'][0]=info_json['text'][0][:startposi]            
    honbun = "\n".join(info_json['text']) #記事配列を改行で繋げるテキストにする。
    if len(honbun)>90:
        page_data['記事本文…'] = EscapeStr(honbun[:90] +'…') #og sns用
    else:
        page_data['記事本文…'] = EscapeStr(honbun) #og sns用
   
    ###########################################カテゴリーリスト作成
    category_arry =[]
    tags_html = ''
    first_category ="anime"#デフォルト
    
    if article_data['baitai_id'] == "in.prw.mantan-web.jp":#共同PRWの場合
        category_id= "release"
        category_arry.append(category_id)
        genre_labels = f'<a href="/{category_id}/" class="label label--article">{CONFIG_JSON["genres"].get(category_id)}</a>'
        first_category =category_id

    else:#通常ジャンルの記事
        sql = f'select * from {CONF.contents_category_tbl} where news_item_id ="{news_item_id}";'
        result = GetDBdata("mantanweb",sql)    
        if result:     
            category_arry = [r["category_id"] for r in result] #カテゴリーをリスト内包表記で作成
            first_category = category_arry[0]

        
        genre_labels = ""
        for category_id in category_arry:
            if "アイドル" in category_id:
                category_url = "matome/アイドル"
            else:
                category_url = category_id
            genre_labels += f'<a href="/{category_url}/" class="label label--article">{CONFIG_JSON["genres"].get(category_id)}</a>'
            
        for tag in tags_arry:#除外タグ対応
            if CONFIG_JSON['genres'].get(tag):#タグidがジャンルにあればそれを表示
                #tags_html +='<a href="'+tag_url+'"><span>#'+CONFIG_JSON['genres'][tag] +'</span></a>'
                #tags_html +=''
                tags_html +='<a href="/matome/'+tag+ '/"><span>#'+tag +'</span></a>' #2023-02-07

            else:                               #なければタグそのものを表記
                #グラビア図鑑、#ファン# ドラマミル #映画上映中 #アニメプレスのタグは非表示
                nodisp = False
                for nodisptags in CONFIG_JSON["nodisp_tags"]:
                    if tag ==  nodisptags:
                        #print("除外タグ"+tag)
                        nodisp =True
                        break
                if nodisp == False:
                    tags_html +='<a href="/matome/'+tag+ '/"><span>#'+tag +'</span></a>' 
        
        if tags_html:
            tags_html ='<div class="article__tag">' +tags_html +'</div>'
    
    page_data['タグリスト'] = tags_html

        
        
    if len(category_arry) >0:
        page_data['ジャンルラベル'] = genre_labels#カテゴリー
        page_data['代表ジャンル名'] = CONFIG_JSON['genres'].get(first_category)#代表カテゴリー
        page_data['カテゴリーID'] = first_category
        page_data['ジャンルurl'] = f'/{first_category}'#カテゴリーURL
        baitai_id = article_data['baitai_id']
        
        if first_category =="release":#共同通信PRワイヤーの場合
            sql = f'select * from {CONF.contents_tbl}  where sts = "open" and baitai_id="{baitai_id}"  order by first_open_datetime desc limit 5;'          
            
        else:
            #2023-01-31 STRAIGHT_JOINに変更速度対策
            #sql = 'select * from contents_tbl STRAIGHT_JOIN contents_category_tbl on contents_tbl.news_item_id= contents_category_tbl.news_item_id where sts = "open" and baitai_id="in.mantan-web.jp" and contents_category_tbl.category_id = "{%category_id%}" order by contents_tbl.first_open_datetime desc limit '+ CONF.latest_list_limit[device]+';'          
            sql = f'''select * from {CONF.contents_tbl} 
                    STRAIGHT_JOIN {CONF.contents_category_tbl} on {CONF.contents_tbl}.news_item_id= {CONF.contents_category_tbl}.news_item_id 
                    where sts = "open" 
                    and baitai_id="in.mantan-web.jp" 
                    and {CONF.contents_category_tbl}.category_id = "{first_category}" 
                    order by {CONF.contents_tbl}.first_open_datetime desc limit {CONF.latest_list_limit[device]}'''
                    
            sql = sql.replace('{%category_id%}',first_category)

        result = GetDBdata('mantanweb',sql)
        
        genre_list_html =''
        page_data['ジャンル記事リスト1']=""
        page_data['ジャンル記事リスト2']=""
        page_data['ジャンル記事リスト3']=""
        page_data['ジャンル記事リスト4以降']=""
        
        for ii,list_data in enumerate(result):
            try:
                genre_list_info_json = json.loads(list_data['info_json'])
                if GetMainKensakuword(genre_list_info_json) =="台紙" or list_data['sns_only'] ==1:
                    continue

            except Exception as e:
                genre_list_info_json ={}
                print(e)
            
            #最新ジャンルリストでPCで６個目以降をテキストにだしわけ
            if device == "pc" and ii >=5:
                genre_list_html = TEMP.genre_li_text.replace('{%記事url%}','/article/'+list_data['news_item_id']+'.html')
            else:
                genre_list_html = TEMP.genre_li[device].replace('{%記事url%}','/article/'+list_data['news_item_id']+'.html')
            
            if list_data['exist_photo'] == 1 and genre_list_info_json.get('image_info'):
                if genre_list_info_json.get('image_info'):
                    image_total_sum = len(genre_list_info_json.get('image_info'))#写真合計枚数
                else:
                    image_total_sum =0
                    
                    
                image_url = ImageUrlCreate(list_data,0,OpenorPreview)#１枚目の画像の情報
                genre_list_html = genre_list_html.replace('{%image_url_thumb2%}',image_url['image_url_thumb2'])
                genre_list_html = genre_list_html.replace('{%image_url_small%}',image_url['image_url_small'])
                genre_list_html = genre_list_html.replace('{%image_url_micro%}',image_url['image_url_micro'])
                genre_list_html = genre_list_html.replace('{%全写真枚数%}',str(image_total_sum))

            else:
                genre_list_html = genre_list_html.replace('{%image_url_thumb2%}','/assets/images/no_image.png')
                genre_list_html = genre_list_html.replace('{%image_url_small%}','/assets/images/no_image.png')
                genre_list_html = genre_list_html.replace('{%image_url_micro%}','/assets/images/no_image.png')
                genre_list_html = genre_list_html.replace('{%全写真枚数%}',"0")


            try:
                genre_list_html = genre_list_html.replace('{%article_date_disp%}',list_data['first_open_datetime'].strftime('%Y年%m月%d日 %H:%M'))
                genre_list_html = genre_list_html.replace('{%article_date_datetime%}',list_data['first_open_datetime'].strftime('%Y-%m-%d'))
            except Exception as e:
                genre_list_html = genre_list_html.replace('{%article_date_disp%}',"")
                genre_list_html = genre_list_html.replace('{%article_date_datetime%}',"")
                
                
            genre_list_html = genre_list_html.replace('{%関連見出し%}',"") #関連見出しは見出しと統合
            kind = GetArticleKind(genre_list_info_json)
            genre_list_html = genre_list_html.replace('{%記事種別%}', '' if kind == '' else f'<span>{kind}</span> ')
            
            if list_data['kanrenmidasi']:#関連見出しがありなしでだしわけ　2015年5月以前は関連見出しがない 
                    kanrenmidasi = list_data['kanrenmidasi']+"："
            else:
                    kanrenmidasi = ""
            
            title = kanrenmidasi + list_data['midasibun']
                                
            if (device =="sp" or device =="amp") and len(title) >= 25:
                    genre_list_html = genre_list_html.replace('{%記事見出し%}',EscapeStr(title[:25]+'…'))
            else:
                    genre_list_html = genre_list_html.replace('{%記事見出し%}',EscapeStr(title))
                
                
            if first_category =="release":#共同通信PRワイヤーの場合
                genre_list_info_json['text'][0] = genre_list_info_json['text'][0].replace('<a href="','').replace('</a>','').replace('"','')
                cut_str="target="
                startposi= genre_list_info_json['text'][0].find(cut_str)    
                genre_list_info_json['text'][0]=genre_list_info_json['text'][0][:startposi]            
                                
                
            if len(genre_list_info_json['text'][0])>90:
                genre_list_html = genre_list_html.replace('{%記事本文…%}',EscapeStr(genre_list_info_json['text'][0][:90]+"…"))
            else:
                genre_list_html = genre_list_html.replace('{%記事本文…%}',EscapeStr(genre_list_info_json['text'][0]))
            
            if ii <3:
                page_data[f'ジャンル記事リスト{ii+1}'] = genre_list_html
                genre_list_html =""
            else:
                 page_data[f'ジャンル記事リスト4以降'] += genre_list_html
                 
    else:
        page_data['ジャンルラベル'] = ""
        page_data['代表ジャンル名'] = ""
        page_data['カテゴリーID'] = ""
        page_data['ジャンルurl'] = ""

   

    #関連外部リンク
    kanren_link_html = ""
    if info_json.get('kanren_link'):
        kanren_link_html='<div class="related__wrap"><h2 class="related__title">関連外部リンク</h2>'
        for kanren_link in info_json['kanren_link']:
            kanren_link_html += f'<div class="related__item related__item--outbound"><a href="{kanren_link["url"]}" target="_blank" rel="nofollow noopener">{kanren_link["name"].replace("URL","")}</a></div>'
        kanren_link_html += '</div>'
    page_data['関連外部リンク'] = kanren_link_html
    

    
    #2023-02-28 ジャンルテーブルがあれば、それをmain_genreに、なければ、GetMainGenre()でメインのジャンルをタグとカテゴリーから決める。
    #注意！！！main_genreは、manga,anime,tvなどがはいる
    if article_data["genre"]:#contents_genre_tblにデータがあるが、日本語（テレビなど）なので、tvなどに変換して、main_genre(URL用)に入れる
        main_genre = article_data["genre"]
        main_genre =[k for k, v in CONFIG_JSON["genres"].items() if v == main_genre][0]
    else:
        #メインのジャンルを取得2023-01-07
        main_genre = GetMainGenre(tags_arry + category_arry)
        
    #ジャンル別ランキング設置###################################################
    if main_genre =="ドラマ" or main_genre =="特撮" or main_genre =="tv":
        genre_ranking_html  = s3.Object(CONF.parts_bucket, CONF.parts_path +"ranking_"+main_genre+".html").get()['Body'].read().decode('utf-8')
    else:
        genre_ranking_html =TEMP.LOGLY_RANKING
    page_data['genre_ranking'] = genre_ranking_html
    ############################################################################


    ############## 2023-02-07 パンくず最適化 2023-04-15写真ページ対応＆処理改良
    #                                        & 2023-03-29 あらすじ、反響・感想パーツ############################################################################
    bread_crumb_list_first ='<li itemscope="" itemprop="itemListElement" itemtype="http://schema.org/ListItem">'
    bread_crumb_list = bread_crumb_list_first

    bread_crumb_list +='<a href="/" itemprop="item"><span itemprop="name">HOME</span></a><meta itemprop="position" content="1"></li>'
    crumb_num =1
    
    bread_crumb_list +=bread_crumb_list_first + '<a href="/{%genre%}" itemprop="item"><span itemprop="name">{%ジャンル名%}</span></a><meta itemprop="position" content="2"></li>'
    crumb_num =2

    #メイン動画タグ
    main_video_tag_html =""

    #関連動画／まとめ情報取得 flexible_infoがあった場合の処理 HOME>ジャンル>まとめ名>記事タイトルまたは、HOME>ジャンル>まとめ名>あらすじ>記事タイトルなど
    related_movie_html =''
    matome_name =""#メイン検索タグ（まとめ名）
    kind =""
    sns_embed_data_html =""

    main_kensaku = GetMainKensakuword(info_json)
    
#    if main_kensaku=="台紙" or article_data["sns_only"] ==1:
    if main_kensaku=="台紙":
        print("GetMainKensakuwordの結果は、台紙")
        print(article_data["sns_only"])

    elif len(tags_arry) >=1:
        matome_name = tags_arry[0]#デフォルト
        bread_crumb_list +=bread_crumb_list_first + '<a href="/matome/{%まとめ名quote%}" itemprop="item"><span itemprop="name">{%まとめ名%}</span></a><meta itemprop="position" content="3"></li>'
        crumb_num =3

    
    if info_json.get('flexible_info'):
        for f_i_data in  info_json['flexible_info']:
            if f_i_data.get('use_name') =="動画タグ" or f_i_data.get('number') =="2" :#number ="2" 関連動画
                print(f"動画タグf_i_data.get('use_name')={f_i_data.get('use_name')}　　{f_i_data.get('number')}")

                if len(f_i_data['value']) == 11:
                    youtube_id = f_i_data['value'] 
                    
                elif len(f_i_data['value'].replace("youtube://","")) ==11:
                    youtube_id = f_i_data['value'].replace("youtube://","")
                    
                else:
                    url = 'http://www.youtube.com/embed/'
                    find_position =f_i_data['value'].find(url)
                    youtube_id = f_i_data['value'][find_position:find_position+len(url)+11].replace(url,'')
                    
                related_movie_html = TEMP.related_movie_html.replace('{%youtube_id%}',youtube_id)
                    
                    
            if f_i_data.get('use_name') =="メイン動画タグ" or f_i_data.get('number') =="14" :#number ="14" メイン動画タグ
                main_video_tag_html = TEMP.main_video_tag_html.replace('{%youtube_id%}',f_i_data['value'] )
                
                
            #まとめパンくず処理  flexible_infoでまとめ情報（article_ext_info)があるかないかで
            if 'article_ext_info' in f_i_data.get('use_name'):#number ="12"
                if f_i_data.get('value')['main_tag']:
                    matome_name = f_i_data.get('value')['main_tag']
                if matome_name =="台紙":
                    matome_name=""
                bread_crumb_list = bread_crumb_list.replace("{%まとめ名quote%}",urllib.parse.quote(matome_name))
                bread_crumb_list = bread_crumb_list.replace("{%まとめ名%}",matome_name)
                print(f"f_i_data.get('value')['kind']={f_i_data.get('value')['kind']}")
                if f_i_data.get('value')['kind'] and f_i_data.get('value')['kind'] !="なし":                #2023-03-01 あらすじなどがあれば
                    kind = "あらすじ" if f_i_data.get('value')['kind'] == "summary" else f_i_data.get('value')['kind'] #あらすじとなっていたら
                    print(f'*****kind={kind}')
                    bread_crumb_list += bread_crumb_list_first + f'<a href="/matome/{urllib.parse.quote(matome_name)}/{urllib.parse.quote(kind)}" itemprop="item"><span itemprop="name">{kind}</span></a><meta itemprop="position" content="4"></li>'
                    crumb_num =4
                    
            if 'sns_embed_data' in f_i_data.get('use_name'):#number ="13"
                #SNS埋め込みデータ#####################
                sns_embed_data_html = CreateSNSembedDataHTML(f_i_data)
        
    
    bread_crumb_list = bread_crumb_list.replace("{%まとめ名quote%}",urllib.parse.quote(matome_name))
    bread_crumb_list = bread_crumb_list.replace("{%まとめ名%}",matome_name)
    page_data['sns埋め込みデータ'] = sns_embed_data_html

    #ジャンル名差込###################################
    if main_genre =="特撮" or main_genre =="ドラマ":#特撮、ドラマは、/matomeをつける2023-02-07
        bread_crumb_list = bread_crumb_list.replace("{%genre%}",f'matome/{main_genre}')
    else:
        bread_crumb_list = bread_crumb_list.replace("{%genre%}",main_genre)

    bread_crumb_list = bread_crumb_list.replace("{%ジャンル名%}",str(CONFIG_JSON["genres"][main_genre]))
    ##################################################

    ####写真ページ用パンくず処理 2023-04-15 
#    if photopage_flg == "photo" or photopage_flg == "photopage" :
    if photopage_flg == "photopage" :
        #print(photo_num)
        bread_crumb_list += bread_crumb_list_first + f'<a href="/article/{news_item_id}.html" itemprop="item"><span itemprop="name">{karen_kijimidasi_all}</span></a><meta itemprop="position" content="{crumb_num+1}"></li>'
        if image_info[photo_num-1]['caption']:
            breadcrumb_caption =f"【写真{photo_num}／{photo_all_sum}枚】" +image_info[photo_num-1]['caption']
        else:
            breadcrumb_caption =f"【写真{photo_num}／{photo_all_sum}枚】"
            
        bread_crumb_list += bread_crumb_list_first + f'<span itemprop="name">{breadcrumb_caption}</span><meta itemprop="position" content="{crumb_num+2}"></li>'
    else:
        bread_crumb_list += bread_crumb_list_first + f'<span itemprop="name">{karen_kijimidasi_all}</span><meta itemprop="position" content="{crumb_num+1}"></li>'

    page_data['breadcrumblist'] = bread_crumb_list

    ##############パンくず処理ここまで###############################################################################################################
    
    page_data['関連動画'] = related_movie_html    
    page_data['メイン動画タグ'] = main_video_tag_html    


    #まとめ記事取得DBアクセス   ##################################################################################################################### 

    #前回のあらすじ
    page_data['前回のあらすじ'] = CreatePrevArasujiHTML(kind,device,matome_name,article_data)
    
    #反響・感想List
    page_data['反響_感想_list'] = CreateHankyoListHTML(kind,device,matome_name,article_data)

    #あらすじ_list
    page_data['あらすじ_list']  = CreateArasujiListHTML(kind,device,matome_name,article_data)
    
    
    ######まとめ関連記事 2023-03-10　################################################################################################################
    matome_related_link_html =""
    if matome_name:
        matome_related_link_html    = CreatematomeRelateHtml(article_data['news_item_id'],matome_name)
        print(f"matome_name={matome_name}")
    page_data['まとめ関連記事']     = matome_related_link_html
    ##ここまで#######################################################################################################################################
    

    #######手動の関連記事リンク付与
    if matome_related_link_html == "":#まとめ関連記事があれば。メイン検索タグ（まとめ名）がなければ、手動関連記事リンクを設置
        related_link_html = CreateRelatedArticleHtml(device,info_json)
    else:
        related_link_html =""
    page_data['関連記事'] = related_link_html
    ##ここまで#######################################################################################################################################
    
    
      
    #HTMLデータ一括差し替え
    for key, value in page_data.items():
        htmldata = htmldata.replace('{%' + key + '%}', str(value))
        
    #ソーシャルURLを貼り付け
    url = 'https://mantan-web.jp/article/'+news_item_id +'.html'    
    htmldata = PutSocialUrls(device,htmldata,article_data['midasibun'],url)

    return htmldata

#SNS埋め込み用HTML作成
def CreateSNSembedDataHTML(f_i_data):
    sns_code_json ={"Youtube":"<div class='Youtube flex-center'><a href='https://m.youtube.com/watch?v={%sns_id%}&amp;feature=youtu.be' target='_blank'><img src='https://i.ytimg.com/vi/{%sns_id%}/hqdefault.jpg'></a></div>",
    "twitter":"<div class='Twitter flex-center'><blockquote class='twitter-tweet'><a href='{%sns_url%}' target='_blank'></a></blockquote><script  src='https://platform.twitter.com/widgets.js' charset='utf-8'></script></div>",
    "instagram_bak":"<div class='instagram flex-center'><blockquote class='instagram-media'><a href='{%sns_url%}' target='_blank'></a></blockquote><script async src='https://www.instagram.com/embed.js'></script></div>",
    "instagram": """ <div class='instagram flex-center'>
                        <blockquote class='instagram-media'
                        data-instgrm-permalink='{%sns_url%}'
                        data-instgrm-version='14'
                        >
                        <a href='{%sns_url%}' target='_blank'></a>
                        </blockquote>
                        <script async src='https://www.instagram.com/embed.js'></script>
                        </div>""",
    "Tiktok" :"<div class='Tiktok flex-center'><blockquote class='tiktok-embed' data-video-id='{%sns_id%}'><a href='https://www.tiktok.com/tiktok/video/{%sns_id%}' target='_blank'></a></blockquote><script async src='https://www.tiktok.com/embed.js'></script></div>"}
    
    
    value = f_i_data.get('value')
    html =""
    for data in value:
        if data.get("sns_embed_url"):
            if "instagram" in data.get("sns_embed_url"):
                sns_name ="instagram"
            elif "twitter" in data.get("sns_embed_url"):
                sns_name ="twitter"
            else:
                continue
            html += sns_code_json[sns_name].replace('{%sns_url%}',data.get("sns_embed_url"))
            
            
    return(html)
#あらすじリスト作成
def CreateArasujiListHTML(kind,device,matome_name,article_data):
    if kind !="あらすじ":
        return("")
        
    midasibun =""
    honbun_summary =""
    article_url = ""
    hit =0
    target_fodt =  article_data["first_open_datetime"]
    limit =50 #取得件数　1/14%
    #2023-04-10 STRAIGHT_JOINでは、速度低下のため、JOINに変更
    sql = f'select * from contents_tbl JOIN contents_tag_tbl on contents_tbl.news_item_id= contents_tag_tbl.news_item_id  where sts = "open" and baitai_id="in.mantan-web.jp" and  contents_tag_tbl.tag = "{matome_name}" order by first_open_datetime desc limit {limit}'
    result = GetDBdata('mantanweb',sql)

    
    if limit > len(result):
        limit =len(result)
    Arasuji_List_Parts =""
    for article_data in result:
        info_json = json.loads(article_data['info_json'])
        if info_json.get("flexible_info"):
            for f_i_data in info_json.get("flexible_info"):
                if f_i_data.get("number") == "12" or  f_i_data.get("use_name") =="article_ext_info":
                    if f_i_data.get('value')['kind'] =="あらすじ":
                        Arasuji_List_Parts+=TEMP.Arasuji_List_Parts.replace("{%title%}",article_data["midasibun"]).replace("{%news_item_id%}",article_data["news_item_id"])
                        hit +=1

        if hit >2:
            break

    if hit ==0:#該当するデータなければ、空で返す。
        return("")


    htmldata = TEMP.Arasuji_List.replace("{%matome_name%}",matome_name).replace("{%Arasuji_List_Parts%}",Arasuji_List_Parts)
    htmldata = htmldata.replace("{%matome_quote%}",urllib.parse.quote(matome_name))

    return(htmldata)   


#2023-03-29 作成前回のあらすじ
def CreatePrevArasujiHTML(kind,device,matome_name,article_data):
    if kind !="あらすじ":
        return("")
        
    midasibun =""
    honbun_summary =""
    article_url = ""
    hit =0
    target_fodt =  article_data["first_open_datetime"]
    limit =20 #取得件数　1/14%
    #2023-04-10 STRAIGHT_JOINでは、速度低下のため、JOINに変更
    sql = f'select * from contents_tbl JOIN contents_tag_tbl on contents_tbl.news_item_id= contents_tag_tbl.news_item_id  where sts = "open" and first_open_datetime <"{target_fodt}" and baitai_id="in.mantan-web.jp" and  contents_tag_tbl.tag = "{matome_name}" order by first_open_datetime desc limit {limit}'
    result = GetDBdata('mantanweb',sql)
    #print("前回のあらすじ")
    if limit > len(result):
        limit =len(result)
        
    for article_data in result:
        info_json = json.loads(article_data['info_json'])
        for f_i_data in info_json.get("flexible_info"):
            if f_i_data.get("number") == "12" or  f_i_data.get("use_name") =="article_ext_info":
                if f_i_data.get('value')['kind'] =="あらすじ" and f_i_data.get('value')['episode']:
                    midasibun = article_data["midasibun"]
                    honbun_summary_1 = info_json["text"][1][:41]+"…"
                    news_item_id =article_data["news_item_id"]
                    article_url=f'/article/{news_item_id}.html'
                    hit +=1
        if hit >0:
            break

    if hit ==0:#該当するデータなければ、空で返す。
        return("")

    if info_json.get("image_info"):
        image_url = f'https://storage.mantan-web.jp{info_json["image_info"][0]["path"]}/001_size2.jpg'
    else:
        image_url ="https://mantan-web.jp/assets/images/no_image.png"#画像なしのサムネール

    htmldata=TEMP.PreArasuji
    
    htmldata = htmldata.replace("{%matome_name%}",matome_name)
    htmldata = htmldata.replace("{%title%}",midasibun)
    htmldata = htmldata.replace("{%honbun_summary_1%}",honbun_summary_1)
    htmldata = htmldata.replace("{%image_url%}",image_url)
    htmldata = htmldata.replace("{%news_item_id%}",news_item_id)
    
    return(htmldata)
    
#2023-03-31 作成　反響_感想List
#2023-04-03 修正
def CreateHankyoListHTML(kind,device,matome_name,article_data):
    if kind !="反響・感想":
        return("")
        
    midasibun =""
    honbun_summary =""
    article_url = ""
    
    #元の記事が何話の情報かを取得
    info_json=json.loads(article_data['info_json'])
    orig_episode_num =""
    for f_i in info_json.get("flexible_info"):
        if (f_i.get("number") == "12" or  f_i.get("use_name") =="article_ext_info") and f_i.get('value')['episode']:
            orig_episode_num = f_i.get('value')['episode']
            break
    
    limit =50 #取得件数　1/14

    news_item_id = article_data["news_item_id"]
    #2023-04-10 STRAIGHT_JOINでは、速度低下のため、JOINに変更
    sql = f'select * from contents_tbl JOIN contents_tag_tbl on contents_tbl.news_item_id= contents_tag_tbl.news_item_id  where sts = "open" and contents_tag_tbl.news_item_id != "{news_item_id}" and baitai_id="in.mantan-web.jp" and  contents_tag_tbl.tag = "{matome_name}" order by first_open_datetime desc limit {limit}'
    #print("反響・感想リストのsql")
    #print(sql)
    result = GetDBdata('mantanweb',sql)
    
    if limit > len(result):
        limit =len(result)
    
    HankyoKansoListPartsStrings=""
    hit =0
    for a_data in result:
        i_json = json.loads(a_data['info_json'])
        if i_json.get("flexible_info"):
            for f_i_data in i_json.get("flexible_info"):
                if (f_i_data.get("number") == "12" or  f_i_data.get("use_name") =="article_ext_info") and f_i_data.get('value')['kind'] =="反響・感想" and f_i_data.get('value')['episode'] ==orig_episode_num :
                    HankyoKansoListPartsStrings +=CreateHankyoKansoListParts(device,a_data,f_i_data)
                    hit +=1
        if hit>1:
            break #２記事まで掲載
    
    if hit == 0:#該当するデータなければ、話数一致しなくて良い最新を作り直す
        HankyoKansoListPartsStrings=""
        for a_data in result:
            i_json = json.loads(a_data['info_json'])
            if i_json.get("flexible_info"):
                for f_i_data in i_json.get("flexible_info"):
                    if (f_i_data.get("number") == "12" or  f_i_data.get("use_name") =="article_ext_info") and f_i_data.get('value')['kind'] =="反響・感想" :
                        news_item_id =a_data["news_item_id"]
                        HankyoKansoListPartsStrings +=  CreateHankyoKansoListParts(device,a_data,f_i_data)
                        hit +=1
                    
            if hit>1:
                break #２記事まで掲載
        
    if hit ==0:
        htmldata =""
    else:
        htmldata= TEMP.HankyoKansoList.replace("{%HankyoKansoListPartsStrings%}",HankyoKansoListPartsStrings)
        htmldata = htmldata.replace("{%matome_name%}",matome_name)
        htmldata = htmldata.replace("{%matome_quote%}",urllib.parse.quote(matome_name))
    
    return(htmldata)
    
#反響・感想リストのパーツを1本生成
def CreateHankyoKansoListParts(device,a_data,f_i_data):
    i_json = json.loads(a_data['info_json'])
    news_item_id =a_data["news_item_id"]


    honbun_summary_1 =""
    
    
    

    if i_json["text"][0] !="":
        if device =="pc":
            honbun_summary_1 = (i_json["text"][1]+i_json["text"][2])[:72]+"…"
        else:
            honbun_summary_1 = (i_json["text"][1]+i_json["text"][2])[:32]+"…"



    article_url=f'/article/{news_item_id}.html'
    if i_json.get("image_info"):
        image_url = f'https://storage.mantan-web.jp{i_json["image_info"][0]["path"]}/001_size2.jpg'
    else:
        image_url ="https://mantan-web.jp/assets/images/no_image.png"#画像なしのサムネール
    HankyoKansoListParts =TEMP.HankyoKansoListParts[device]
    on_air_date_arry = f_i_data.get('value')['on_air_date'].split("-")
    HankyoKansoListParts = HankyoKansoListParts.replace("{%title%}",a_data["kanrenmidasi"]+"："+a_data["midasibun"])
    HankyoKansoListParts = HankyoKansoListParts.replace("{%honbun_summary_1%}",honbun_summary_1)
    HankyoKansoListParts = HankyoKansoListParts.replace("{%image_url%}",image_url)
    HankyoKansoListParts = HankyoKansoListParts.replace("{%news_item_id%}",news_item_id)

    return(HankyoKansoListParts)

#####関連記事リンク5本HTMLリスト作成##################
def CreateRelatedArticleHtml(device,info_json):
    #関連記事　2022-12-19　複数関連記事設置 arai
    related_link_html = ""
    mkanren_link_count =0
    if info_json.get('mkanren_link'):
        related_link_html ='<div class="related__wrap"><h2 class="related__title">【関連記事】</h2>'
        for mkanren_link in info_json["mkanren_link"]:
            
            if "http://rcm-jp.amazon.co.jp/e/cm" not in mkanren_link["name"]:#amazon　アフィリエイトタグを無視
                mkanren_link["url"] = mkanren_link["url"].replace("http://","https://")
                mkanren_link["url"] = mkanren_link["url"].replace("/amp/","/")
                if "https://mantan-web.jp/20" in mkanren_link["url"]:
                    mkanren_link["url"] = mkanren_link["url"].replace("https://mantan-web.jp/20","https://mantan-web.jp/article/20")
                    str_len1 =len('https://mantan-web.jp/article/')
                    str_len2 =str_len1 + len('/2011/12/31')
                    mkanren_link["url"] = mkanren_link["url"][:str_len1] + mkanren_link["url"][str_len2:]

                
                if "/movie/" in mkanren_link["url"]:
                    m_id =mkanren_link["url"].replace("https://maidigitv.jp/movie/","").replace("https://mantan-web.jp/movie/","")
                    m_id = m_id[:11]
                    img_html = f'https://i.ytimg.com/vi/{m_id}/hqdefault.jpg'
                    mkanren_link_count +=1

                elif "https://maidigitv.jp/article/" in mkanren_link["url"]:
                    img_html = f'/assets/images/no_image.png'
                    mkanren_link_count +=1
                    
                #2023-07-18 追加　gravure.mantan-web.jpのURLの場合のポリシーチェック(news_item_idを取得)
                elif "gravure.mantan-web.jp/article/" in mkanren_link["url"] or "gravure.mantan-web.jp/photo/" in mkanren_link["url"]:
                    m_id =mkanren_link["url"].replace("https://gravure.mantan-web.jp/article/","").replace("https://gravure.mantan-web.jp/photo/","")
                    m_id=m_id[:24]
                    policy_result = PolicyChk(m_id)
                    if policy_result["tag_k"] ==1:
                            continue

                    img_html = f'https://storage.mantan-web.jp/images/{m_id[:4]}/{m_id[4:6]}/{m_id[6:8]}/{m_id}/001_size2.jpg'
                    mkanren_link_count +=1
                    
                elif "/photo/" in mkanren_link["url"] or "/article/" in mkanren_link["url"]:
                    m_id =mkanren_link["url"].replace("https://mantan-web.jp/article/","").replace("https://mantan-web.jp/photo/","")
                    m_id=m_id[:24]
                    policy_result = PolicyChk(m_id)
                    if policy_result["tag_k"] ==1:
                            continue

                        
                    #######　関連記事のサムネールがあるかないか 　#####################################################
                    image_prefix = f"storage/images/{m_id[:4]}/{m_id[4:6]}/{m_id[6:8]}/{m_id}/001_size2.jpg"
                    filelist = s3cli.list_objects(Bucket="mantan-web.jp", Prefix=image_prefix) #画像がS3にあるかどうかチェック
                    if "Contents" in filelist:
                        img_html = f'https://storage.mantan-web.jp/images/{m_id[:4]}/{m_id[4:6]}/{m_id[6:8]}/{m_id}/001_size2.jpg'
                        #print("サムネールあり")
                    else:
                        img_html = f'/assets/images/no_image.png'
                        #print("サムネールがありません")
                    ###################################################################################################
                    mkanren_link_count +=1
                elif "/gallery/" in mkanren_link["url"]:
                    m_id =mkanren_link["url"].replace("https://mantan-web.jp/gallery/","")[11:]
                    m_id=m_id[:24]
                    img_html = f'https://storage.mantan-web.jp/images/{m_id[:4]}/{m_id[4:6]}/{m_id[6:8]}/{m_id}/001_size2.jpg'
                    mkanren_link_count +=1
                else:
                   img_html = f'/assets/images/no_image.png'

                related_link_html += '<div class="related__item p0"><a href="'+mkanren_link["url"]+'" class="related__list_unit">'
                related_link_html += f'<div><img src="{img_html}" class="related__item--photo"></div>'
                related_link_html += f'<div class="related__item--text">{mkanren_link["name"]}</div>'
                related_link_html += f'</a></div>'
        related_link_html +="</div>"
        if mkanren_link_count ==0:
            related_link_html =""


    if device =="amp":
        related_link_html = related_link_html.replace("iframe","amp-iframe")
    
    return(related_link_html)
     
    
####################　まとめ関連記事HTML作成　##########################################
def CreatematomeRelateHtml(news_item_id,matome_name):
    limit =6
    matome_related_link_html = f'<div class="related__wrap"><h2 class="related__title">【{matome_name} 関連記事】</h2>%s</div>'
    related_list_html = ""
    
    #SQLはSTRAIGHT_JOINでは遅くなるのでJOINに！
    sql = f'select * from contents_tbl JOIN contents_tag_tbl on contents_tbl.news_item_id= contents_tag_tbl.news_item_id  where sts = "open" and sns_only!=1 and contents_tbl.news_item_id != "{news_item_id}" and baitai_id="in.mantan-web.jp" and  contents_tag_tbl.tag = "{matome_name}" order by first_open_datetime desc limit {limit}'
    result = GetDBdata('mantanweb',sql)
    article_sum =0
    if limit > len(result):
        limit =len(result)
        
    for ii in range(limit):
        info_json = json.loads(result[ii]['info_json'])
        related_list_html += TEMP.matome_related_link_html_tmp

        related_list_html = related_list_html.replace("{%news_item_id%}",result[ii]["news_item_id"])
        if result[ii]["kanrenmidasi"]:
            related_list_html = related_list_html.replace("{%midasibun%}",result[ii]["kanrenmidasi"]+"："+result[ii]["midasibun"])
        else:
            related_list_html = related_list_html.replace("{%midasibun%}",result[ii]["midasibun"])
            
        m_id=result[ii]["news_item_id"][:24]
        if info_json.get("image_info"):
            image_url = f'https://storage.mantan-web.jp/images/{m_id[:4]}/{m_id[4:6]}/{m_id[6:8]}/{m_id}/001_size2.jpg'
        else:
            image_url = "/assets/images/no_image165x109.png"
        related_list_html = related_list_html.replace("{%image_url%}",image_url)
        article_sum +=1
        if article_sum >=6:
            break
        
    if related_list_html !="" and article_sum >=4:
        matome_related_link_html = f'<div class="related__wrap"><h2 class="related__title">【{matome_name} 関連記事】</h2>{related_list_html}</div>'
    else:
        matome_related_link_html =""
        

    return(matome_related_link_html)

def CreateMatomeBox(main_kensaku, news_item_id):
    ### matomebox ###
    matomebox_render_html = ""
    matomesql = f'''
        select 
            matome_box,
            contents_tbl.news_item_id,
            kanrenmidasi,
            midasibun,
            info_json
        from matome_tbl 
        left join contents_tag_tbl on contents_tag_tbl.tag = matome_tbl.matome_name
        left join contents_tbl on contents_tag_tbl.news_item_id = contents_tbl.news_item_id
        where matome_name = "{main_kensaku}"
        and matome_box_flg = 1
        and status="open"
        and sts="open"
        -- and contents_tbl.news_item_id <> "{news_item_id}"
        order by contents_tbl.first_open_datetime desc
        limit 1
    '''
    matome_result = GetDBdata("mantanweb", matomesql)

    if matome_result:
        matomebox_data = json.loads(matome_result[0]["matome_box"])
        
        matomebox_btn_html = ""
        for matomebox in matomebox_data:
            
            if matomebox["flag"]:
                matomebox_btn_parts = TEMP.matomebox_btn_parts
                matomebox_btn_parts = matomebox_btn_parts.replace('{%matomebox_btn_link%}', matomebox["link"])
                matomebox_btn_parts = matomebox_btn_parts.replace('{%matomebox_btn_name%}', matomebox["name"])
                
                matomebox_btn_html = matomebox_btn_html + matomebox_btn_parts
        
        matomebox_html = TEMP.matomebox_parts
        matomebox_html = matomebox_html.replace('{%matomebox_btn%}', matomebox_btn_html)
        
        image_url = ImageUrlCreate(matome_result[0],0,"open") #画像のbaseurlを返す
        matomebox_html = matomebox_html.replace('{%matome_image_url%}', image_url["image_url_mid"])
        matomebox_html = matomebox_html.replace('{%matome_image_caption%}', matome_result[0]["kanrenmidasi"] + ":"+ matome_result[0]["midasibun"])
        
        matomebox_html = matomebox_html.replace('{%matome_article_title%}', matome_result[0]["kanrenmidasi"] + ":"+ matome_result[0]["midasibun"])
        
        matomebox_html = matomebox_html.replace('{%matome_name%}', main_kensaku)
        
        url = f'/article/{matome_result[0]["news_item_id"]}.html'
        matomebox_html = matomebox_html.replace('{%matome_link%}', url)
        
        matomebox_render_html = matomebox_render_html + matomebox_html

    return matomebox_render_html
    #htmldata = htmldata.replace('{%matomebox%}', matomebox_render_html)
    ### matomebox end ###
    
########################################################################################
def GetMainGenre(tag_and_category_arry):
    main_genre ="anime"
    #特撮→ドラマ→アニメ→ ゲーム→マンガ→グッズ→テレビ→映画→芸能
    genre_list=["特撮","ドラマ","anime","game","manga","goods","tv","cinema","entama","music","release"]
    for j in genre_list:
        for tc in tag_and_category_arry:
            if tc == j:
                main_genre = tc
                return main_genre
    return main_genre
def PutSocialUrls(device,htmldata,kijimidashi,url):
    if device =="amp":
        htmldata = htmldata.replace('{%Twitterシェアurl%}',"https://twitter.com/share?original_referer=" + urllib.parse.quote(url) +'&amp;via=mantaweb&amp;text='+urllib.parse.quote(kijimidashi))
        htmldata = htmldata.replace('{%はてなシェアurl%}','')

    else:
        #2023-03-17 original_referer  をurl=に変更
        htmldata = htmldata.replace('{%Twitterシェアurl%}',"https://twitter.com/share?url=" + urllib.parse.quote(url) +'&amp;via=mantanweb&amp;text='+urllib.parse.quote(kijimidashi))
        htmldata = htmldata.replace('{%はてなシェアurl%}',"http://b.hatena.ne.jp/add?mode=confirm&amp;url=" + urllib.parse.quote(url) +'&amp;text='+urllib.parse.quote(kijimidashi))
    return htmldata
   
#画像のbaseurlを返す    
def ImageUrlCreate(articledata,num,OpenorPreview):
#    CONFIG_JSON = json.loads(s3.Object(CONF.config_file_bucket, CONF.config_file).get()['Body'].read().decode('utf-8'))

    news_item_id = articledata['news_item_id']
    info_json = json.loads(articledata['info_json'])
    orig_path=""
    image_url_mid=""
    image_url_orig=""
    
    if info_json.get('image_info'):
        image_info =info_json['image_info'][num]
        size_num = len(info_json['image_info'][num]['size'])
        size_micro  = 2
        if size_num <=4:
            size_small  = 2
            size_mid    = 2
            size_orig   = 2
            
        elif size_num <=7:
            size_small  = 3
            size_mid    = size_num -2
            size_orig   = size_num -2            
        elif size_num ==8:
            size_small  = 4
            size_mid    = size_num -2
            size_orig   = size_num -2            
        else:
            size_small  = 4
            size_mid    = 6
            size_orig   = size_num -2 #最高画質size10に
            
        if "prm" in news_item_id:
            size_micro  = 5
            size_small  = 5
            size_mid    = 5
            size_orig   = 5            
            
        image_url_thumb2= CONFIG_JSON['image_storage_urls'][OpenorPreview]  + image_info['path']+'/'+image_info['filename']['basename']+'_'+f'thumb2.'+image_info['filename']['ext']
        image_url_small= CONFIG_JSON['image_storage_urls'][OpenorPreview]  + image_info['path']+'/'+image_info['filename']['basename']+'_'+f'size{size_small}.'+image_info['filename']['ext']
        image_url_mid= CONFIG_JSON['image_storage_urls'][OpenorPreview]  + image_info['path']+'/'+image_info['filename']['basename']+'_'+f'size{size_mid}.'+image_info['filename']['ext']
        image_url_orig= CONFIG_JSON['image_storage_urls'][OpenorPreview]  + image_info['path']+'/'+image_info['filename']['basename']+'_'+f'size{size_orig}.'+image_info['filename']['ext']
        orig_path=  CONFIG_JSON['image_storage_paths'][OpenorPreview] + image_info['path']+'/'+image_info['filename']['basename']+'_'+f'size{size_orig}.'+image_info['filename']['ext']
        mid_path=  CONFIG_JSON['image_storage_paths'][OpenorPreview] + image_info['path']+'/'+image_info['filename']['basename']+'_'+f'size{size_mid}.'+image_info['filename']['ext']
        small_path=  CONFIG_JSON['image_storage_paths'][OpenorPreview] + image_info['path']+'/'+image_info['filename']['basename']+'_'+f'size{size_mid}.'+image_info['filename']['ext']
        image_url_micro= CONFIG_JSON['image_storage_urls'][OpenorPreview]  + image_info['path']+'/'+image_info['filename']['basename']+'_'+f'size{size_micro}.'+image_info['filename']['ext']
           
    else:
        image_url_thumb2='/assets/images/no_image.png'
        image_url_small='/assets/images/no_image.png'
        image_url_orig='/assets/images/no_image.png'
        image_url_mid='/assets/images/no_image.png'
        image_url_micro='/assets/images/no_image.png'
        orig_path=''
        small_path=''
        mid_path=''
        size_num =0
    size ={"width":0,"height":0}                
    return{'size_num':size_num,'image_url_orig':image_url_orig,'image_url_small':image_url_small,'image_url_mid':image_url_mid,'image_url_micro':image_url_micro,'image_url_thumb2':image_url_thumb2,'orig_path':orig_path,'mid_path':mid_path,'small_path':small_path}
    
    
def GetImageSize(bucket,key):
    download_path = '/tmp/{}{}'.format(uuid.uuid4(), key.replace('/', '')) 
    try:
        s3cli.download_file(bucket, key, download_path)
        image = Image.open(download_path)
        width,height = image.size
        
    except Exception as e:
        print("GetImageSize エラー詳細＝ "+str(e))
        (width,height) = (0,0)
        
    return{"width":width,"height":height}
    
    
#バンダイタグ
def BandaiTage(htmldata,keywords):

    tag=""
    if keywords =="":
        return(htmldata.replace("{%bandai_tag%}",tag))
        
    for conf_key in CONFIG_JSON['bandai_tag'].keys():
        if str(keywords).find(conf_key) != -1:
            tag= TEMP.bandai_tag
            tag= tag.replace("{%offerid%}",CONFIG_JSON['bandai_tag'][conf_key][0])
            tag= tag.replace("{%image%}",CONFIG_JSON['bandai_tag'][conf_key][1])
            htmldata =htmldata.replace("{%bandai_tag%}",tag)
            break
    
    htmldata =htmldata.replace("{%bandai_tag%}","")

    if str(keywords).find("プレミアムバンダイ") != -1:
        htmldata =htmldata.replace("{%premium_bandai_tag%}",TEMP.premium_bandai_tag)

    else:
        htmldata =htmldata.replace("{%premium_bandai_tag%}","")

    return(htmldata)


    
#共通HTMLの結合差し込み処理      
def PartsAssemble(htmldata,device):
    try:
        if device =='pc':
            #PC　記事詳細ページ(article）用動画最新リスト（MAiDiGiTV　動画）
            latest_movie_list_for_articlepage_html  = s3.Object(CONF.parts_bucket, CONF.parts_path + "latest_movie_list_for_articlepage.html").get()['Body'].read().decode('utf-8')
            htmldata = htmldata.replace("{%MAiDiGiTV動画%}",latest_movie_list_for_articlepage_html)
    
        hash_parts_html  = s3.Object(CONF.parts_bucket, CONF.parts_path + CONFIG_JSON['Html_parts']['hash_parts_html'][device]).get()['Body'].read().decode('utf-8')
        htmldata = htmldata.replace("{%hash_parts_html%}",hash_parts_html)
    
    except Exception as e:
        print(f'S3コピーエラー {e}')
       
    return htmldata   
    

def CreateHebiroteHtml():
    hebirote_html_parts = TEMP.hebirote_html_parts
    data = s3.Object(CONF.parts_bucket, 'storage/items/hebirote.json').get()['Body'].read().decode('utf-8')
    
    jsonData = json.loads(data)
    
    lists = []
    
    for item in jsonData['data']:
        today = datetime.datetime.now()  + timedelta(hours=9)
        start_at = datetime.datetime.strptime(item['startAt'], '%Y-%m-%d %H:%M')
        
        if item['endAt']:
            end_at = datetime.datetime.strptime(item['endAt'], '%Y-%m-%d %H:%M')
        else:
            end_at = datetime.datetime.now(JST) + timedelta(hours=9)
            
        if item['display'] and start_at < today and today < end_at:
            lists.append(item)
    
    if len(lists) == 0:
        return ""
    
    result = random.choice(lists)
    
    hebirote_html_parts = hebirote_html_parts.replace('{%hebirote_title%}', result['title'])
    hebirote_html_parts = hebirote_html_parts.replace('{%hebirote_img_url%}', result['photoUrl'])
    hebirote_html_parts = hebirote_html_parts.replace('{%hebirote_link_url%}', update_query(result['linkUrl'], 'ext_m', 'h'))
    return hebirote_html_parts
    
# GETパラメータを変更＆追加してくれる関数
def update_query(url, key, new_val):
    pr = urllib.parse.urlparse(url)
    d = urllib.parse.parse_qs(pr.query)
    d[key] = new_val
    return urllib.parse.urlunparse(pr._replace(query=urllib.parse.urlencode(d, doseq=True)))




def DbConnect(media):
    #データーベース接続
    connection = pymysql.connect(
            host=CONF.rds_host,
            user=CONF.db_user,
            password=CONF.db_password,
            db=CONF.db_name[media],
            cursorclass=pymysql.cursors.DictCursor)
    #JSTに変更        
    sql = "SET SESSION time_zone = CASE WHEN POSITION('rds' IN CURRENT_USER()) = 1 THEN 'UTC' ELSE 'Asia/Tokyo' END;"
    with connection.cursor() as cur:
        cur.execute(sql)
        result = cur.fetchall()
        connection.commit()
        cur.close()
    return connection
    
def GetDBdata(media,sql):
    connection = DbConnect(media)
    #DBからデータを取得
    try:
        with connection.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
            connection.commit()
            cur.close()

    except Exception as e:
        print('処理エラー：詳細＝')
        print(e)
        print(sql)
        return

    connection.close() #DB Close
    return result

def EscapeStr(moji):
    moji = moji.replace('"',"&quot;")# ダブルクォーテーション
    #moji = moji.replace('“',"&quot;")# ダブルクォーテーション
    moji = moji.replace("'","&#39;")#シングルクォーテーション
    moji = moji.replace("<","&lt;")#
    moji = moji.replace(">","&gt;")#
    moji = moji.replace("&","&amp;")#アンパサンド
    
    return(moji)
    
#過去の修正履歴
#2022-04-12     ハッシュタグにカテゴリーが入らないように修正　タグのみ
#2022-05-13     共同通信PRWタグを空文字埋め
#2022-05-23     画像なし
#2022-06-03     amp-iframe対応
#2022-06-03     共同通信prw　noindex対応
#2022-06-13     ダブルクォーテーション、シングルクォーテンションをエスケープ処理
#2022-06-19     写真なしにも関わらず、photoパラメーターをつけてクロールされた場合の対応。exist_photo==1でなければ、写真特集ページは表示しない。
#2022-06-27     photo=xxxで写真枚数以上の指定があった場合は、404にする
#2022-07-xx     /test/対応
#2022-07-13     写真ありなのに写真ない場合の対応
#2022-07-14     変更タイトル対応　flexible_infoに変更タイトル(タイトル変更)があった場合の対応
#2022-07-31     /photo/xxxxxxxxx.html?photo=xxxx対応 galleryも対応
#2022-08-05     変更タイトルをphotoページにも対応（origin templateも変更）
#2022-08-08     キャプションとaltを区別してエスケープ処理　InsertPhotoAndPreNextData()　　template.pyも変更
#2022-10-03     まとめパンくず対応
#2022-10-16     記事見出しのEscape処理　JSON、OGtitleのみエスケープ処理をする
#2022-10-17     記事詳細ページでの写真サイズの記載変更　pxを追加とaspect-ratio追加
#2022-10-20     パンくずのURLをURLエンコーディング対応
#2022-10-20     aspect-ratio をwidth heightに変更
#2022-10-31     Twitterなどog:image、twitter:image用 sns.jpgがあれば、それを使用する
#2022-11-01     写真特集の写真をmid から　origに変更　InsertPhotolistData()
#2022-11-09     写真特集の写真をorig から　midに戻す。　InsertPhotolistData()
#2022-11-11     写真特集の写真をorig 戻し、最高画質をsize9にする　InsertPhotolistData()
#0222-12-19     関連記事追加
#2023-01-06     関連記事で/amp/削除、サムネールをsize2に変更
#2023-01-25     本文中へのキーワードリンク　まとめページへのリンク 2023-01-25実装
#2023-01-26     404エラーでのレスポンスステータスコードを404にする。
#2023-01-27     公開時間を表示 article_date_disp
#2023-01-29     order by をcontents_category_tbl.news_item_idに変更して、速度対策
#2023-01-30     301リダイレクト処理
#2023-02-07     パンくず最適化対応
#2023-02-28     contents_genre_tblからジャンルを取得する(left_join)、なければ、Getmaigenre()で生成。
#2023-03-01     パンくず最適化追加対応
#2023-03-02     パンくず最適化バグ修正
#2023-03-13     関連記事にまとめ関連記事付与を追加　まとめ名が指定されている場合は、まとめ関連記事リストを掲出
#   〃          写真専用ページ新設対応    
    
