import requests
import time
from urllib.parse import urlparse, urljoin
import re
import unicodedata
import concurrent.futures
import platform
import sys
import warnings
from playwright.sync_api import sync_playwright  
from gliner import GLiNER  
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline 
from deep_translator import GoogleTranslator  
from PIL import Image
import io
from dotenv import load_dotenv
import os
if platform.system() == "Windows":
    import winsound

load_dotenv()

warnings.filterwarnings("ignore", message=".*pin_memory.*")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="gliner")

# ================= USER CONFIGURATION =================
MAX_CONCURRENT_BROWSERS = 12  # Safe limit for Phase 1
TOTAL_TARGET = int(input("How many URLs to process: "))

# ================= USER CONFIGURATION =================
API_BASE_URL = os.environ.get("API_BASE_URL")
API_HOSTNAME = urlparse(API_BASE_URL).netloc
PORTAL_TOKEN = os.environ.get("PORTAL_TOKEN")
EXTENSION_TOKEN = os.environ.get("EXTENSION_TOKEN")



# ================= API ENDPOINTS =================
URL_GET_LIST = API_BASE_URL + "/api/instances-get"
URL_UPDATE_INSTANCE = API_BASE_URL + "/api/instances/update"
URL_TRIGGER_CRAWL = API_BASE_URL + "/api/instances"
URL_CHECK_STATUS = API_BASE_URL + "/api/instance/detail"
URL_MARK_SUCCESS = API_BASE_URL + "/api/instance/updateFailedReview"

# ================= HEADERS =================
headers_portal = {
    "authority": API_HOSTNAME,
    "authorization": PORTAL_TOKEN,
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

headers_extension = {
    "authority": API_HOSTNAME,
    "authorization": EXTENSION_TOKEN,
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# ================= LOAD MODELS =================
print("⏳ Loading AI Models...")
st_time = time.time()

tokenizer = AutoTokenizer.from_pretrained("Davlan/bert-base-multilingual-cased-ner-hrl")
model_davlan = AutoModelForTokenClassification.from_pretrained(
    "Davlan/bert-base-multilingual-cased-ner-hrl"
)
ner = pipeline(
    "ner", model=model_davlan, tokenizer=tokenizer, aggregation_strategy="simple"
)


model = GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")

print(f"✅ Models Loaded! (Time: {time.time() - st_time:.2f}s)")

# ================= HELPER FUNCTIONS =================``
def beep(frequency=2000, duration=1000):
    if platform.system() == "Windows":
        winsound.Beep(frequency, duration)
        
def clean_text(text):
    """Normalize and clean text for consistent detection."""
    normalized = unicodedata.normalize("NFKC", text)
    return re.sub(r"[^\w\s-]", "", normalized).strip()

def get_fake_paused_instances():
    try:
        
        response = requests.post(
            URL_GET_LIST,
            headers=headers_portal,
            json={
                "page": 1,
                "per_page": 50,
                "error_type": ["invalid_source"],
                "manual_error": True,
            },
        )
        if response.status_code == 200:
            instances = response.json().get("instances", [])
            return instances
    except:
        return None
    return None

def get_latest_instance():
    try:
        response = requests.post(
            URL_GET_LIST,
            headers=headers_portal,
            json={"page": 1, "per_page": 5, "filters": {}},
            
        )
        if response.status_code == 200:
            instances = response.json().get("instances", [])
            # print(instances)
            if instances:
                return instances[0:2]
    except:
        return None
    return None

def update_instance_error(instance_id, error_type, error_reason, manual_error=True):
    try:
        requests.post(
            URL_UPDATE_INSTANCE,
            headers=headers_portal,
            json={
                "instance_id": instance_id,
                "error_type": error_type,
                "error_reason": error_reason,
                "manual_error": manual_error,
            },
        )
        return True
    except:
        return False

def check_country_code(instance_id):
    try:
        response = requests.get(
            f"{URL_CHECK_STATUS}?instance_id={instance_id}", headers=headers_portal
        )
        if response.status_code == 200:
            return response.json().get("instance", {})
    except:
        pass
    return {}

def verify_view_crawled_text(id):
    try:
        response = requests.get(
            f"{URL_CHECK_STATUS}?instance_id={id}", headers=headers_portal
        )
        if response.status_code == 200:
            extracted_entities = response.json().get("extracted_entities", [])

            
            if extracted_entities and len(extracted_entities) > 0:
                first_entity = extracted_entities[0]

                
                rawhtml = first_entity.get("raw_html", "")
                


                if "This site can't be reached" in rawhtml:
                    print("This Site cant be reached in the VIEW")
                    return {"status": "proxy_issue"}
                
                elif "Performing security verification" in rawhtml:
                    print("Performing security verification in the VIEW")
                    return {"status": "google_captcha_v2"}

                elif "Sorry, you have been blocked" in rawhtml:
                  print("Sorry, you have been blocked IN THE VIEW")
                  return {"status": "proxy_issue"}    


                return True
        else:
            print("else run response not 200")
            return False

    except:
        print("verify view name failed")
        return False

def verify_screenshot(instance_id):
    """Fetches instance details, retrieves the screenshot, and verifies its height."""
    try:
        url = f"{URL_CHECK_STATUS}?instance_id={instance_id}"
        response = requests.get(url, headers=headers_portal)

        if response.status_code == 200:
            
            screenshot_path = (
                response.json()
                .get("instance", {})
                .get("screenshots", {})
                .get("start_ss")
            )

            if not screenshot_path or not isinstance(screenshot_path, str):
                print("❌ No valid screenshot path found in the API response.")
                return False  

        
            full_img_url = urljoin("https://extention.amlwatcher.com", screenshot_path)
            print(full_img_url)

            # 3. Fetch the actual image data
            img_response = requests.get(full_img_url, headers=headers_portal)

            if img_response.status_code == 200:
                image = Image.open(io.BytesIO(img_response.content))
                width, height = image.size
                print(f"height: {height}\n width: {width}")

                
                if height < 363:
                    return False
                else:
                    return True
            else:
                print(
                    f"❌ Failed to download the image. Status Code: {img_response.status_code}"
                )
                return False

    except Exception as e:
        print(f"❌ Error processing instance {instance_id}: {e}")

    return False

def check_crawl_status(instance_id):
    try:
        response = requests.get(
            f"{URL_CHECK_STATUS}?instance_id={instance_id}", headers=headers_portal
        )
        return (
            response.json().get("instance", {}).get("status")
            if response.status_code == 200
            else "unknown"
        )
    except:
        return "unknown"

def mark_review_success(target_url):
    try:
        requests.post(
            URL_MARK_SUCCESS, headers=headers_portal, json={"url": target_url}
        )
        return True
    except:
        return False

def trigger_crawl(target_url, node_id):
    try:
        hostname = urlparse(target_url).netloc
        if node_id == None:
            node_id = int(time.time() * 1000)
        payload = {
            "nodes": [
                {
                    "key": "",
                    "merging_strategy": {"parent_selector": None, "type": "order"},
                    "node_id": "start_url_node",
                    "node_name": "start_url",
                    "url": target_url,
                },
                {
                    "key": "raw_html",
                    "node_id": node_id,
                    "node_name": "extract",
                    "select_mode": "css",
                    "selector": "html>body",
                    "selector_type": "html",
                },
            ],
            "run_llm": False,
            "full_page_llm": True,
            "url": target_url,
            "hostname": hostname,
        }

        return (
            requests.post(
                URL_TRIGGER_CRAWL, headers=headers_extension, json=payload
            ).status_code
            == 201
        )
    except:
        return False

# ================= PHASE 1: TEXT DETECTION (PARALLEL SAFE) =================
def detect_names_phase1(url, id, confidence_threshold=0.67):
    """
    Checks Text using GLiNER. If no names, returns Image URLs for later processing.
    """
    try:
        raw_text = ""
       
        unwanted_keywords = [
    "հհ նախagahի",'државен секретар', "საკრებულოს", "თავჯდომარე", "საკრებულოს თავჯდომარე",
    "საკრებულოს თავმჯდომარე", "research staff", "tajemník městského úřadu",
    "místostarosta", "кмета на общината", "președintelui consiliului județean",
    "consiliului", "președintelui", "главният секретар", "вашето име",
    "primarului orașului sulina", "кметът на район", "областния управител",
    "главен секретар", "областния", "областен управител", "monitorul oficial local",
    "oficial local", "управител", "профил", "medic primar voluntar", "medic",
    "primar", "voluntar", "купувача", "președintele româniei", "кмета", "общината",
    "Председател", "consilier personal", "consilier", "personal", "Заместник",
    "директор", "министъра", "здравеопазването", "Talijanski", "veleposlanik",
    "osoba", "Povjerljiva", "gradonačelnika", "Zamjenik", "potpredsjednikaice",
    "secretarul orasului hirlau", "POTPREDSJEDNICI", "PREDSJEDNIK", "skupštine",
    "Županijske", "imenovani", "presedintele romaniei", "predstavnici", "kupcem",
    "secretar general", "drugog", "potraživanja", "önkormányzati", "képviselő",
    "State", "Secretary", "Minister", "Secretary-General", "Embajador", "Prefeito",
    "Municipal", "stellv", "Vorsitzender", "Bürgermeister", "unlautere",
    "Anzeigenwerber", "Bürgermeisterin", "Donau", "Mayor", "Beigeordneter",
    "Mitarbeiter", "A bis Z", "secretar", "general",'author'
]
        keywords_lower = [keyword.lower() for keyword in unwanted_keywords]

     
        sorted_keywords = sorted(keywords_lower, key=len, reverse=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )


            context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type in ["image", "media", "font"]
                    else route.continue_()
                ),
            )

            page = context.new_page()
            try:
                page.goto(url, timeout=100000, wait_until="networkidle")
                raw_text = page.inner_text("body")
                raw_text = raw_text[:-70]
                raw_text = raw_text.lower()
                cleaned_text = raw_text
                for keyword in sorted_keywords:
                    cleaned_text = cleaned_text.replace(keyword, "")


                cleaned_text = " ".join(cleaned_text.split())

                

            except:
                return {"status": "url timeout cannot open url"}
            browser.close()

        if not cleaned_text:
            return {"status": "no_content"}


        unique_names = set()
        labels = ["person"]  


        chunk_size = 1200
        chunks = [
            cleaned_text[i : i + chunk_size]
            for i in range(100, len(cleaned_text), 1000) ]  # 200 overlap

        instance_detail = check_country_code(id)
        country_codes = instance_detail.get("country_codes", [])
        country_code = country_codes[0] if country_codes else "unknown"

        unwanted_set = {
            u.lower() for u in unwanted_keywords
        } 


          ## if want to use DAVLAN BERT model
        if country_code == "np":
            for chunk in chunks:
                entities = ner(chunk)
                for ent in entities:
                    if (
                        ent["entity_group"] == "PER"
                        and ent["score"] >= confidence_threshold
                    ):
                        raw_name = ent["word"].strip()
                        normalized = unicodedata.normalize("NFKC", raw_name)
                        clean_name = re.sub(r"[^\w\s-]", "", normalized).strip().lower()

                        if len(clean_name) > 2:
                            unique_names.add(raw_name)
                if len(unique_names) >= 2:
                    break

            if unique_names:
                return {"status": "success", "names": list(unique_names)}


            return {"status": "no name found"}
        
        ## for Gliner
        else:
            for chunk in chunks:
                entities = model.predict_entities(
                    chunk, labels, threshold=confidence_threshold
                )

                for ent in entities:
                    raw_name = ent["text"].strip()
                    cleaned_name = clean_text(raw_name)

                    name_parts = cleaned_name.split()
                    filtered_parts = [
                        word for word in name_parts if word.lower() not in unwanted_set
                    ]
                    final_name = " ".join(filtered_parts)


                    if (
                        len(final_name) >= 3
                        and len(final_name.split()) >= 2
                        # and len(final_name.split()) < 5
                    ):
  
                        unique_names.add(final_name)

                    if len(unique_names) >= 3:
                        break    

                

            if unique_names:
                return {"status": "success", "names": list(unique_names)}


            return {"status": "no name found"}

    except Exception as e:
        print(f"Error in Phase 1: {e}")
        return {"status": "error"}

# ================= WORKER FUNCTION (PARALLEL PHASE) =================
def process_parallel_phase(instance_data):
    i_id = instance_data["id"]
    full_url = instance_data["url"]
    node_id = instance_data["nodeId"]
    print(f"🚀 [Phase 1] Checking Text: {full_url}")

    hostname = urlparse(full_url).netloc
    instance_detail = check_country_code(i_id)
    country_codes = instance_detail.get("country_codes", [])
    country_code = country_codes[0] if country_codes else "unknown"

# ================= for direct execution =================
    if hostname == "parliament.bg" or country_code == "bn":
        print("exporthungary website crawling without checkings")
        if trigger_crawl(full_url, node_id):
            # Monitor
            for _ in range(100):
                status = check_crawl_status(i_id)
                if status == "success":
                    ValidViewText = verify_view_crawled_text(i_id)
                    if ValidViewText:
                        update_instance_error(i_id, None, None, False)
                        mark_review_success(full_url)
                        print(f"   🎉 Task Completed: {full_url}")
                        return
                    elif ValidViewText["status"] == "proxy_issue":
                        update_instance_error(
                            i_id, "proxy_issue", "names not crawled", True
                        )
                        print(f"  ❌ MOVING TO PROXY ISSUE {full_url}")
                        if trigger_crawl(full_url, node_id):
                            print("crawled the proxy instance to verify")
                            return
                        else:
                            print(
                                "Extension sei Crawl fail hogya!! moving to invalid reason trigger failed:"
                            )
                            return
                    elif ValidViewText["status"]== "google_captcha_v2":
                        update_instance_error(
                            i_id, "google_captcha_v2", "Human verification", True
                        )
                        print(f"  ❌ MOVING TO Google CAPTCHA V2 {full_url}")
                        if trigger_crawl(full_url, node_id):
                            print("crawled the CAPTCH V2 instance to verify")
                            return
                        else:
                            print(
                                "Extension sei Crawl fail hogya!! moving to invalid reason trigger failed:"
                            )
                            return

                elif status == "failed":
                    update_instance_error(
                        i_id, "deo_backend_issues", "crawl_failed", True
                    )
                    print(" Crawl Failed Moving to deo_backend_issues(crawl_failed)")
                    return
                time.sleep(5)
        else:
            print(
                "Extension sei Crawl fail hogya!! moving to invalid reason trigger failed:"
            )
            update_instance_error(i_id, "invalid_source", "trigger failed", True)

    else:
        result = detect_names_phase1(full_url, i_id)

        if result["status"] == "success":
            original_names = result["names"]
            translated_names = []

            try:

                translator = GoogleTranslator(source="auto", target="en")
                translated_names = [
                    translator.translate(name) for name in original_names
                ]
            except Exception as e:
                translated_names = ["(Translation Failed)"]

            print(f"   ✅ Name found (Orignal language)): {original_names}")
            print(
                f"  🟨 🇺🇸 Name found (Eng):  {translated_names} -- \n{full_url} 🟨"               
            )
            print("   Triggering Crawl...")

            if trigger_crawl(full_url, node_id):
                for _ in range(100):
                    status = check_crawl_status(i_id)
                    if status == "success":
                        isViewName = verify_view_crawled_text(i_id)
                        if isViewName:
                            update_instance_error(i_id, None, None, False)
                            mark_review_success(full_url)
                            print(f"   🎉 Task Completed: {full_url}")
                            return
                        elif isViewName["status"] == "proxy_issue":
                            update_instance_error(i_id, "proxy_issue", "names not crawled", True)
                            print(f"  ❌ MOVING TO PROXY ISSUE {full_url}")
                            if trigger_crawl(full_url, node_id):
                                print("crawled the proxy instance to verify")
                                return
                            else:
                                print("Extension sei Crawl fail hogya!! moving to invalid reason trigger failed:")
                                return
                        elif isViewName["status"]== "google_captcha_v2":
                            update_instance_error(
                                i_id, "google_captcha_v2", "Human verification", True
                            )
                            print(f"  ❌ MOVING TO Google CAPTCHA V2 {full_url}")
                            if trigger_crawl(full_url, node_id):
                                print("crawled the CAPTCH V2 instance to verify")
                                return
                            else:
                                print(
                                    "Extension sei Crawl fail hogya!! moving to invalid reason trigger failed:"
                                )
                                return
                        

                    elif status == "failed":
                        update_instance_error(
                            i_id, "deo_backend_issues", "crawl_failed", True
                        )
                        print(
                            " Crawl Failed Moving to deo_backend_issues(crawl_failed)"
                        )
                        return
                    time.sleep(4)
            else:
                print(
                    "Extension sei Crawl fail hogya!! moving to invalid reason trigger failed:"
                )
                update_instance_error(i_id, "invalid_source", "trigger failed", True)

        elif result["status"] == "no name found":
            print(
                f"❌ No text name might be in Images check for OCR yourself. Added INVALID SOURCE: {full_url}"
            )
            update_instance_error(i_id, "invalid_source", "no name", True)

        elif result["status"] == "url timeout cannot open url":
            print("⚠️ timeout waited for 100000ms no response - moving to Source Issue")
            update_instance_error(i_id, "source_issue", "website not opening....", True)

        elif result['status'] == "google_captcha_v2":
          update_instance_error(i_id, "google_captcha_v2", "human verification", True)
          print(f"  ❌ MOVING TO PROXY ISSUE {full_url}")
          if trigger_crawl(full_url, node_id):
            print("crawled the proxy instance to verify")

        else:
            print(
                "❌ Website se kuch data nhi extract hua!! Moving to Invalid ,Reason: error/empty"
            )
            update_instance_error(i_id, "invalid_source", "error/empty", True)

def main():
    start_time = time.time()
    processed_count = 0
    consecutive_no_work = 0


    print("STARTING PHASE 1: PARALLEL TEXT CHECKS")
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_CONCURRENT_BROWSERS
    ) as executor:
        futures = []
        while processed_count < TOTAL_TARGET:
            candidates = get_latest_instance()

            if not candidates:
                time.sleep(2)
                continue

            target_inst = None


            for inst in candidates:
                status = inst.get("status") 
                error = inst.get("error_type")

                if status == "pending" and error == None:
                    target_inst = inst
                    break  

            # --- IF NO VALID INSTANCE FOUND IN TOP 2 ---
            if not target_inst:
                print("Waiting for new url (Top 2 are completed/error)")
                consecutive_no_work += 1

                if consecutive_no_work == 20:
                    print("20 iterations passed no new work, waiting for 15 min....")
                    try:
                        beep()
                    except:
                        pass
                

                if consecutive_no_work > 400:
                    print("🛑 No more work found.")
                    break

                time.sleep(3)
                continue

            # --- IF VALID INSTANCE FOUND ---
            consecutive_no_work = 0
            i_id = target_inst.get("id")
            details = target_inst.get("instance_detail")
            
            if details:
                node_id = details[1].get("node_id") if len(details) > 1 else None
                full_url = details[0].get("url")
            else:
                node_id = None
                full_url = target_inst.get("url", "")

            if full_url.lower().endswith(".pdf"):
                update_instance_error(i_id, "data_in_document", "in pdf", True)
                processed_count +=1
                continue

            # Pause & Submit
            if update_instance_error(i_id, "invalid_source", "NO NAME!", True):
                processed_count += 1
                futures.append(
                    executor.submit(
                        process_parallel_phase,
                        {"id": i_id, "url": full_url, "nodeId": node_id},
                    )
                )
                print(f"   Queueing :    {processed_count}/{TOTAL_TARGET}")
                time.sleep(1)

        # Wait for all parallel tasks to finish
        concurrent.futures.wait(futures)

    # ----------------------------------------------------
    # FINISH
    # ----------------------------------------------------

    rem_batch_instances = get_fake_paused_instances()
    valid_batch = []
    for inst in rem_batch_instances:
        reason = inst.get("error_reason", "").lower().strip()

        if reason == "NO NAME!":
            valid_batch.append(inst)

    if not valid_batch:
        print("####### NO Instance left to check and crawl ############")

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for inst in valid_batch:
            i_id = inst.get("id")
            full_url = inst.get("url", "")
            futures.append(
                executor.submit(
                    process_parallel_phase,
                    {"id": i_id, "url": full_url, "nodeId": None},
                )
            )

        # Wait for this batch to finish Phase 1
        concurrent.futures.wait(futures)

    print(f"\n✅✅✅ ALL TASKS COMPLETED ({processed_count}) ✅✅✅")

    try:
        beep()
    except:
        pass

    end_time = time.time()
    print(f"Total Time: {(end_time -start_time)/60:.2f} minutes")

if __name__ == "__main__":
    main()
