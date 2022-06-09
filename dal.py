#! /usr/bin/env python
# Public domain; Mr.Z-man, MZMcBride; 2012

import datetime
from email.MIMENonMultipart import MIMENonMultipart
from email.header import Header
import htmlentitydefs
import urllib
import re
import smtplib
import sys
import textwrap
import traceback

import BeautifulSoup
import wikitools

import config

DEBUG_MODE = False
if sys.argv[-1] == '--debug':
    DEBUG_MODE = True

# Establish a few wikis
metawiki_base = 'https://meta.wikimedia.org'
metawiki = wikitools.Wiki(metawiki_base+'/w/api.php'); metawiki.setMaxlag(-1)
enwiki_base = 'https://en.wikipedia.org'
enwiki = wikitools.Wiki(enwiki_base+'/w/api.php'); enwiki.setMaxlag(-1)
enwikt_base = 'https://en.wiktionary.org'
enwikt = wikitools.Wiki(enwikt_base+'/w/api.php'); enwikt.setMaxlag(-1)
enquote_base = 'https://en.wikiquote.org'
enquote = wikitools.Wiki(enquote_base+'/w/api.php'); enquote.setMaxlag(-1)

# Figure out the date
date = datetime.datetime.utcnow()
year = date.year
day = date.day
month = date.strftime('%B')
if DEBUG_MODE:
    print(month, day, year)

# Empty list
final_sections = []

def strip_html(original_text):
    soup = BeautifulSoup.BeautifulSoup(original_text, fromEncoding='utf-8')
    new_text = ''.join(soup.findAll(text=True)).encode('utf-8')
    return new_text

def parse_wikitext(wiki, wikitext):
    params = {'action' : 'parse',
              'text'   : wikitext,
              'disablepp' : 'true'}
    req = wikitools.api.APIRequest(wiki, params)
    response = req.query()
    parsed_wikitext = response[u'parse'][u'text'][u'*']
    return parsed_wikitext

def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == '&#':
            # character reference
            try:
                if text[:3] == '&#x':
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub('&#?\w+;', fixup, text)

def make_featured_article_section(month, day, year):
    page_title = '%s/%s %s, %s' % ("Wikipedia:Today's featured article",
                                   month,
                                   day,
                                   year)
    try:
        wikitext = wikitools.Page(enwiki, page_title).getWikiText()
    except wikitools.page.NoPage:
        return False
    parsed_wikitext = parse_wikitext(enwiki, wikitext)
    wrapper_div = u'<div class="mw-parser-output">'
    if parsed_wikitext.startswith(wrapper_div):
        parsed_wikitext = parsed_wikitext.replace(wrapper_div, '')
    # Grab the first <p> tag and pray
    found = False
    for line in parsed_wikitext.split('\n'):
        if line.startswith('<p>') and not found:
            first_para = line
            found = True
    p_text = first_para.rsplit('. (', 1)[0]+'.'
    p_text = unescape(p_text)
    clean_p_text = strip_html(p_text)
    if (first_para.find('. (') is not -1 and
        first_para[:100].find('._(') is not -1):
        more_html = first_para.rsplit('. (', 2)
        more_html = '. ('.join([more_html[1], more_html[2]])
    elif first_para.find('. (') is not -1:
        more_html = first_para.rsplit('. (', 1)[1]
    elif first_para.find('." (') is not -1:
        more_html = first_para.rsplit('." (', 1)[1]
    else:
        more_html = first_para
    more_soup = BeautifulSoup.BeautifulSoup(more_html)
    for a in more_soup.findAll('a'):
        read_more = ('%s' + '<%s%s>') % ('Read more: ',
                                         enwiki_base,
                                         a['href'].encode('utf-8').replace('(', '%28').replace(')', '%29'))
        featured_article_title = a['title'].encode('utf-8')
    featured_article_section = '\n'.join([wrap_text(clean_p_text),
                                          '',
                                          read_more,
                                          ''])
    final_sections.append(featured_article_section)
    return featured_article_title

def make_selected_anniversaries_section(month, day):
    page_title = 'Wikipedia:Selected anniversaries/%s %s' % (month, day)
    parsed_wikitext = parse_wikitext(enwiki, '{{'+page_title+'}}')
    anniversaries = []
    for line in parsed_wikitext.split('\n'):
        if line.startswith('<li') and line.find(u'\u2013') != -1:
            line = line.replace(' <i>(pictured)</i> ', ' ')
            line = line.replace(' <i>(pictured)</i>, ', ', ')
            line = re.sub(r'<span class="nowrap">(.+?)</span>', r'\1', line)
            plaintext_lines = wrap_text(strip_html(unescape(line)))
            formatted_plaintext_lines = ':\n\n'.join(plaintext_lines.split(' \xe2\x80\x93 ', 1))
            line_soup = BeautifulSoup.BeautifulSoup(line)
            for b in line_soup.findAll('b'):
                if (len(b.contents) == 3 and
                    (b.contents[0] == b.contents[2] == u'"')):
                    b.contents.pop()
                    b.contents.pop(0)
                if (len(b.contents) == 2 and
                    b.contents[1] == u"'"):
                    b.contents.pop()
                for a in b.contents:
                    read_more = ('<%s%s>') % (enwiki_base,
                                              a['href'].encode('utf-8').replace('(', '%28').replace(')', '%29'))
            complete_item = formatted_plaintext_lines+'\n'+read_more+'\n'
            anniversaries.append(complete_item)
    header = '_______________________________\n'
    header += 'Today\'s selected anniversaries:\n'
    selected_anniversaries_section = '\n'.join([header,
                                                '\n'.join(anniversaries)])
    final_sections.append(selected_anniversaries_section)
    return

def make_wiktionary_section(month, day, year):
    page_title = 'Wiktionary:Word of the day/%s/%s %s' % (year, month, day)
    if DEBUG_MODE:
        print(enwikt_base + '/wiki/' + page_title.replace(' ', '_'))
    parsed_wikitext = parse_wikitext(enwikt, '{{'+page_title+'}}')
    soup = BeautifulSoup.BeautifulSoup(parsed_wikitext, fromEncoding='utf-8')
    word = soup.find('span', id='WOTD-rss-title').string.encode('utf-8')

    definitions_stripped = []
    for li in soup.findAll('li'):
        li_contents = li.renderContents()
        nested_soup = BeautifulSoup.BeautifulSoup(li_contents, fromEncoding='utf-8')
        # Remove nested li elements, by removing any nested ol elements,
        # since the li elements will be processed later separately
        for ol in nested_soup.findAll('ol'):
            ol.decompose()
        li_contents = nested_soup.renderContents()
        def_ = unescape(strip_html(li_contents).decode('utf-8')).strip()
        definitions_stripped.append(def_)
    definitions = []
    if len(definitions_stripped) > 1:
        for i, t in enumerate(definitions_stripped):
            definitions.append(str(i + 1) + '. ' + t)
    elif len(definitions_stripped) == 1:
        definitions = definitions_stripped
    if not definitions:
        return
    definitions = map(wrap_text, definitions)

    header = '_____________________________\n'
    header += 'Wiktionary\'s word of the day:\n'
    read_more = '<'+enwikt_base+'/wiki/'+urllib.quote(word.replace(' ', '_'))+'>'
    wiktionary_section = '\n'.join([header,
                                    word+':',
                                    '\n'.join(definitions),
                                    read_more,
                                    ''])
    if DEBUG_MODE:
        print(repr(wiktionary_section))
    final_sections.append(wiktionary_section.encode('utf-8'))
    return

def make_wikiquote_section(month, day, year):
    page_title = 'Wikiquote:Quote of the day/%s %s, %s' % (month, day, year)
    parsed_wikitext = parse_wikitext(enquote, '{{'+page_title+'}}')
    lines = []
    for line in parsed_wikitext.split('\n'):
        if line.find('~') != -1:
            author_soup = BeautifulSoup.BeautifulSoup(line)
            for a in author_soup.findAll('a'):
                if not a.string:
                    continue
                read_more = ('<%s%s>') % (enquote_base,
                                          a['href'].encode('utf-8').replace('(', '%28').replace(')', '%29'))
                author = '  --'+a.string.encode('utf-8')
        elif line != u'in<br />':
            lines.append(unescape(line))
    authorless_lines = '\n'.join(lines)
    quote = strip_html(authorless_lines)
    quote = quote.strip()
    header = '___________________________\n'
    header += 'Wikiquote quote of the day:\n'
    wikiquote_section = '\n'.join([header,
                                   wrap_text(quote),
                                   author,
                                   read_more])
    final_sections.append(wikiquote_section)
    return

def wrap_text(text):
    wrapped_lines = textwrap.wrap(text, width=72)
    return '\n'.join(wrapped_lines)

def send_email(email_to, email_from, email_subject, email_body):
    msg = MIMENonMultipart('text', 'plain')
    msg['Content-Transfer-Encoding'] = '8bit'
    msg.set_payload(email_body, 'utf-8')
    msg['From'] = email_from
    msg['Subject'] = Header(email_subject, 'utf-8')
    server = smtplib.SMTP(config.smtp_host, config.smtp_port)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(email_from, config.email_password)
    for addr in email_to:
        msg['To'] = addr
        body = msg.as_string()
        server.sendmail(email_from, addr, body, '8bitmime')
    server.quit()

send = False
try:
    # Do some shit
    featured_article_title = make_featured_article_section(month, day, year)
    subject = '%s %d: %s' % (month, day, featured_article_title)
    make_selected_anniversaries_section(month, day)
    make_wiktionary_section(month, day, year)
    make_wikiquote_section(month, day, year)

    final_output = '\n'.join(final_sections)
    send = True

except:  # Unnamed!
    # Inform the wiki of an issue!
    date = '%s %s, %s' % (month, day, year)
    tb = traceback.format_exc().rstrip().replace(config.wiki_password, 'XXX')
    if DEBUG_MODE:
        print(tb)
        sys.exit(1)
    else:
        talk_page = wikitools.Page(metawiki, config.notification_page)
        metawiki.login(config.wiki_username, config.wiki_password)
        text = '\n'.join(("Just thought you'd like to know:",
                          "<pre>",
                          tb,
                          "</pre>",
                          "Love, --~~~~"))
        talk_page.edit(text=text,
                       summary='daily-article-l delivery failed (%s)' % date,
                       section='new',
                       bot=1)

if DEBUG_MODE:
    print(subject + '\n')
    print('\n'.join(final_sections))
elif send:
    send_email(config.to_addresses,
               config.from_address,
               subject,
               final_output)
