import datetime
import json
import os
import re
import zipfile
from urllib.parse import urljoin
from urllib.request import urlretrieve

import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from PyPDF2 import PdfFileMerger
from requests.adapters import HTTPAdapter

header = {
    "User-Agent": "PostmanRuntime/7.20.1",
    "Accept": "*/*",
    "Cache-Control": "no-cache",
    "Postman-Token": "8eb5df70-4da6-4ba1-a9dd-e68880316cd9,30ac79fa-969b-4a24-8035-26ad1a2650e1",
    "Host": "medianet.edmond-de-rothschild.fr",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "cache-control": "no-cache",
}


class Day:
    NOW = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    YEAR = str(NOW.year).zfill(4)
    MONTH = str(NOW.month).zfill(2)
    DAY = str(NOW.day).zfill(2)
    DATE = "".join([YEAR, MONTH, DAY])
    print(DATE)

    DIR = os.path.join("Download", DATE)
    PAGES_FILE_PATH = os.path.join(DIR, f"证券时报{DATE}.zip")
    MERGED_FILE_PATH = os.path.join(DIR, f"证券时报{DATE}.pdf")
    EBOOK_FILE_PATH = os.path.join(DIR, f"证券时报{DATE}.epub")
    EBOOK_IMAGE_PATH = os.path.join(DIR, "images")

    HOME_URL = f"http://epaper.stcn.com/paper/zqsb/html/{YEAR}-{MONTH}/{DAY}/node_2.htm"
    print(HOME_URL)

    s = requests.Session()
    s.mount("http://", HTTPAdapter(max_retries=3))
    HOME_CONTENT = s.get(HOME_URL)
    print(HOME_CONTENT.status_code)
    if HOME_CONTENT.status_code != requests.codes.ok:
        print("Stopped: Status 404")
        raise SystemExit(1)

    if HOME_CONTENT.encoding == "ISO-8859-1":
        encodings = requests.utils.get_encodings_from_content(HOME_CONTENT.text)
        if encodings:
            encoding = encodings[0]
        else:
            encoding = HOME_CONTENT.apparent_encoding

        HOME_CONTENT = HOME_CONTENT.content.decode(
            encoding, "replace"
        )  # 如果设置为replace，则会用?取代非法字符

    # print(HOME_CONTENT)
    PAGE_LIST = re.findall(f'<dt id="....">', HOME_CONTENT)
    PAGE_LIST = [item[-6:-2] for item in PAGE_LIST]
    print(PAGE_LIST)

    if len(PAGE_LIST) == 0:
        PAGE_LIST = re.findall(f"<dt id=....>", HOME_CONTENT)
        PAGE_LIST = [item[-5:-1] for item in PAGE_LIST]
        print(PAGE_LIST)

    if PAGE_LIST == []:
        print("Stopped: No Page")
        raise SystemExit(1)

    PAGE_NAME_LIST = re.findall("版<i>(.*?)</i>", HOME_CONTENT)
    TOTAL_COUNT = int(re.findall(r"\d+", PAGE_NAME_LIST[0])[0])

    ADJ_PAGE_LIST = []
    ADJ_PAGE_NAME_LIST = []
    for i in range(len(PAGE_NAME_LIST)):
        if PAGE_NAME_LIST[i] != "信息披露":
            ADJ_PAGE_LIST.append(PAGE_LIST[i])
            ADJ_PAGE_NAME_LIST.append(PAGE_NAME_LIST[i])

    PAGE_COUNT = len(ADJ_PAGE_LIST)
    print(PAGE_COUNT)

    soup = BeautifulSoup(HOME_CONTENT, "html.parser")
    PAGES_CONTENT = [str(tag.dd) for tag in soup.find_all("dl")]

    if not os.path.isdir(DIR):
        os.makedirs(DIR)

    if not os.path.isdir(EBOOK_IMAGE_PATH):
        os.makedirs(EBOOK_IMAGE_PATH)


class Page:
    def __init__(self, HOME_CONTENT, name, page_content, page: str):
        self.page = page
        self.name = "第" + self.page + "版: " + name
        self.html_url = f"http://epaper.stcn.com/paper/zqsb/html/{Day.YEAR}-{Day.MONTH}/{Day.DAY}/node_2.htm"
        self.html = HOME_CONTENT
        self.page_content = page_content
        self.pdf = requests.get(
            (
                "http://epaper.stcn.com/paper/zqsb/page/1/{0}-{1}/{2}/{3}/{0}{1}{2}{3}_pdf.pdf".format(
                    Day.YEAR, Day.MONTH, Day.DAY, page
                )
            ),
            header,
        ).content
        self.path = os.path.join(Day.DIR, f"{self.page}.pdf")

    def __str__(self) -> str:
        return f"{self.__class__.__name__}" f"[date={Day.DATE}, page={self.page}]"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def title(self):
        return self.name

    @property
    def articles(self):
        output_article_list = []
        html_components = re.findall(f"content_........htm", self.page_content)
        article_titles = re.findall(f'.htm">(.*?)</a></li>', self.page_content)
        for i in range(len(html_components)):
            article_html = "http://epaper.stcn.com/paper/zqsb/html/{}-{}/{}/{}".format(
                Day.YEAR, Day.MONTH, Day.DAY, html_components[i]
            )
            output_article_list.append((article_html, article_titles[i]))
        return output_article_list

    def save_pdf(self):
        with open(self.path, "wb") as f:
            f.write(self.pdf)


def main():
    pages = [
        Page(
            Day.HOME_CONTENT,
            Day.ADJ_PAGE_NAME_LIST[idx],
            Day.PAGES_CONTENT[idx],
            page_str,
        )
        for idx, page_str in enumerate(Day.ADJ_PAGE_LIST)
    ]
    pages_file = zipfile.ZipFile(Day.PAGES_FILE_PATH, "w")
    merged_file = PdfFileMerger(False)
    data = {
        "date": Day.DATE,
        "page_count": str(Day.PAGE_COUNT),
        "pages_file_path": Day.PAGES_FILE_PATH,
        "merged_file_path": Day.MERGED_FILE_PATH,
        "ebook_file_path": Day.EBOOK_FILE_PATH,
        "release_body": (
            f"# [{Day.DATE}]({Day.HOME_URL})" f"\n\n今日 {Day.TOTAL_COUNT} 版"
        ),
    }

    # Create ebook
    book = epub.EpubBook()
    book.set_identifier(f"ZQSB{Day.DATE}")
    book.set_title(f"证券时报{Day.DATE}")
    book.set_language("zh-Hans")
    book.add_author("证券时报")

    style = """BODY { text-align: justify;}"""

    default_css = epub.EpubItem(
        uid="style_default",
        file_name="style/default.css",
        media_type="text/css",
        content=style,
    )
    book.add_item(default_css)

    ebook_toc_list = []
    book.spine = ["nav"]

    ebook_page_count = 1

    print("Start Processing!")
    # Process
    for page in pages:
        # Save pdf
        page.save_pdf()

        # Pages file
        pages_file.write(page.path, os.path.basename(page.path))

        # Merged file
        merged_file.append(page.path)

        # Data
        data["release_body"] += f"\n\n## [{page.title}]({page.html_url})\n"

        ebook_page = epub.EpubHtml(
            title=page.title.replace("<br/>", " "),
            file_name=f"{ebook_page_count:02d}.xhtml",
            lang="zh-Hans",
        )
        ebook_page.content = f"<body><h1>{page.title}</h1></body>"
        ebook_page.add_item(default_css)

        book.add_item(ebook_page)
        book.spine.append(ebook_page)

        ebook_section = epub.Section(page.title, f"{page.title}.xhtml")
        ebook_article_list = []
        ebook_article_count = 1

        for article in page.articles:
            data["release_body"] += f"\n- [{article[1]}]({article[0]})"

            response = requests.get(article[0])
            soup = BeautifulSoup(response.content, "html.parser")
            content = soup.select_one("div.tc_con")

            for div in content.find_all("div", {"class": "tc_news_tit"}):
                div.decompose()
            for div in content.find_all("ul", {"class": "tc_news_list"}):
                div.decompose()

            ebook_image_count = 1
            for img in content.select("img"):
                src = img.get("src")
                img_extension = src.split(".")[-1]
                img_absolute_url = urljoin(article[0], src)

                img_filename = f"{ebook_page_count:02d}{ebook_article_count:02d}{ebook_image_count:02d}.{img_extension}"

                img_path = os.path.join(
                    os.path.join(
                        Day.EBOOK_IMAGE_PATH,
                        img_filename,
                    )
                )
                urlretrieve(img_absolute_url, img_path)
                with open(img_path, "rb") as f:
                    ebook_image = epub.EpubItem(
                        file_name=f"images/{img_filename}",
                        media_type=f"image/{img_extension}",
                        content=f.read(),
                    )
                    book.add_item(ebook_image)
                img["src"] = f"images/{img_filename}"

                ebook_image_count += 1

            ebook_article = epub.EpubHtml(
                title=article[1].replace("<br/>", " "),
                file_name=f"{ebook_page_count:02d}{ebook_article_count:02d}.xhtml",
                lang="zh-Hans",
            )
            ebook_article.content = f"<body><h2>{article[1]}</h2>{content.prettify(formatter='html')}</body>"
            ebook_article.add_item(default_css)
            book.add_item(ebook_article)
            book.spine.append(ebook_article)
            ebook_article_list.append(ebook_article)
            ebook_article_count += 1

        ebook_toc_list.append((ebook_section, tuple(ebook_article_list)))
        ebook_page_count += 1

        # Info
        print(f"Processed {page}")

    # Save
    # pages_file.close()
    merged_file.write(Day.MERGED_FILE_PATH)
    merged_file.close()
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    book.toc = tuple(ebook_toc_list)

    # add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # define css style
    with open("nav.css", "r") as f:
        style = f.read()

    # add css file
    nav_css = epub.EpubItem(
        uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style
    )
    book.add_item(nav_css)

    epub.write_epub(Day.EBOOK_FILE_PATH, book, {})


if __name__ == "__main__":
    main()
