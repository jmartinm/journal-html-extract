#!/usr/bin/env python

import argparse
import codecs
import cStringIO
import csv
import os

from bs4 import BeautifulSoup


class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    https://docs.python.org/2/library/csv.html#csv-examples
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def extract_from_elsevier(html, csvfile):
    soup = BeautifulSoup(html, 'html.parser')

    # Find the emails
    emails_html = soup.find_all('a', 'auth_mail')
    emails = [email.attrs['href'].split(':')[1] for email in emails_html]

    # Find corresponding authors
    corresponding_authors = []
    for email in emails_html:
        for element in email.previous_siblings:
            try:
                author_name = (
                    element.text if 'authorName' in element.attrs.get(
                        'class', []) else ''
                )
                if author_name:
                    corresponding_authors.append(author_name)
            except AttributeError:
                pass

    # Find the date
    date_html = soup.find_all('p', 'volIssue')[0]
    date = [date_html.text.split(',')[1].strip()]

    csvfile.writerow(corresponding_authors + emails + date)


def extract_from_wiley(html, csvfile):
    if not html or 'Page has moved' in html:
        # Empty file, skip
        return
    soup = BeautifulSoup(html, 'html.parser')

    # Find the email
    email = []
    try:
        email_html = soup.select('a[href^=mailto]')
        email = [email_html[0].text]
    except IndexError:
        pass

    # Find the corresponding author

    corresponding_author = []
    try:
        for parent in email_html[0].parents:
            if getattr(parent, 'attrs', None) and 'data-author-name' in parent.attrs:
                corresponding_author = [parent.attrs['data-author-name']]
                break
    except IndexError:
        pass

    # Find the date
    date = []
    try:
        date = [soup.select('time[id=first-published-date]')[0].text]
    except IndexError:
        pass

    csvfile.writerow(corresponding_author + email + date)


def extract_from_springer(html, csvfile):
    soup = BeautifulSoup(html, 'html.parser')

    if soup.find_all('body', 'articles'):
        # Summary page, skip it
        return

    # Find the corresponding authors and emails
    corresponding_authors = []
    emails = []

    author_list_html = soup.select('li[itemprop="author"]')
    if author_list_html:
        for author in author_list_html:
            email_selector = author.select('a[href^=mailto]')
            if email_selector:
                emails.append(email_selector[0].attrs['href'].split(':')[1])
                corresponding_authors.append(author.text.split('\n')[1])
    else:
        # Seems to be Rice articles
        emails_html = soup.select('a[href^=mailto]')
        for email in emails_html:
            emails.append(email.attrs['href'].split(':')[1])
            for sibling in email.previous_siblings:
                if getattr(sibling, 'attrs', None) and 'AuthorName' in sibling.attrs.get('class', []):
                    corresponding_authors.append(sibling.text)

    # Find the date
    try:
        date = [soup.find_all("time")[0].text]
    except IndexError:
        date = [soup.find_all('p', 'HistoryOnlineDate')[
            0].text.split(':')[1].strip()]

    csvfile.writerow(corresponding_authors + emails + date)


def guess_type_of_file(file_content):
    """ Guess whether the given file is from Elsevier, wiley or Springer."""
    soup = BeautifulSoup(file_content, 'html.parser')

    if soup.find_all('span', 'spElsevierPubIcon'):
        return extract_from_elsevier
    elif soup.select('meta[content^=Springer]'):
        return extract_from_springer
    else:
        return extract_from_wiley


def main(args):
    initial_path = os.path.abspath(args.folder)

    csv_filename = os.path.basename(initial_path).replace(' ', '_')
    with open(csv_filename + '.csv', 'wb') as csvfile:
        for root, subdirs, files in os.walk(initial_path):
            for file in files:
                name, extension = os.path.splitext(file)
                if extension.startswith('.ht') or args.all:
                    file_path = os.path.join(root, file)
                    file_content = open(file_path).read()
                    extract_fn = guess_type_of_file(file_content)
                    if extract_fn:
                        csvwriter = UnicodeWriter(csvfile)
                        extract_fn(file_content, csvwriter)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", help="folder to start looking for files")
    parser.add_argument("-a", "--all", action="store_true",
                        help="check all files (not only .html extension)")
    args = parser.parse_args()
    main(args)
