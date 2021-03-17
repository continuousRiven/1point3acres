import requests
import urllib.parse
import re
from PIL import Image
from process_gif import get_code_from_gif
import xml.dom.minidom as xml
import lxml.html as html
import questions
from sys import exit
import os

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0"
referer = "https://www.1point3acres.com/bbs/"
login_url = "https://www.1point3acres.com/bbs/member.php?mod=logging&action=login&loginsubmit=yes&infloat=yes&lssubmit=yes&inajax=1"
login_url_v2 = "https://www.1point3acres.com/bbs/member.php?mod=logging&action=login&loginsubmit=yes&infloat=yes&lssubmit=yes&inajax=1"

get_verify_code_url = "https://www.1point3acres.com/bbs/misc.php?mod=seccode&action=update&idhash=%s&inajax=1&ajaxtarget=seccode_%s"
check_verify_code_url = "https://www.1point3acres.com/bbs/misc.php?mod=seccode&action=check&inajax=1&&idhash=%s&secverify=%s"

get_checkin_url = "https://www.1point3acres.com/bbs/dsu_paulsign-sign.html"
post_checkin_url = "https://www.1point3acres.com/bbs/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=0&inajax=0"

get_question_url = "https://www.1point3acres.com/bbs/plugin.php?id=ahome_dayquestion:pop&infloat=yes&handlekey=pop&inajax=1&ajaxtarget=fwin_content_pop"
post_answer_url = "https://www.1point3acres.com/bbs/plugin.php?id=ahome_dayquestion:pop"

cookie_jar = None


def save_error(response: requests.Response, error_desc: str = ""):
	print(f"{error_desc} 未知错误，查看tmp.html，了解详情")
	tmpfilename = "tmp.html"
	if os.name == "posix":
		tmpfilename = "/tmp/" + tmpfilename
	f = open("tmp.html", "w", encoding="utf-8")
	f.write(response.request)
	f.close()


def check_status_code(response: requests.Response, error_desc: str = ""):
	if response.status_code != 200:
		print(f"{error_desc} error: status code is {response.status_code}")
		exit(-1)


def login(username: str, password_hashed: str):
	global cookie_jar
	print("do login....")
	header = {
		"User-Agent": user_agent,
		'Content-Type': 'application/x-www-form-urlencoded',
	}
	body = {
		"username": username,
		"password": password_hashed,
		"cookietime": "2592000",  # 30 days
		"quickforward": "yes",
		"handlekey": "ls",
	}
	response = requests.post(login_url, headers=header, data=urllib.parse.urlencode(body))
	cookie_jar = response.cookies
	check_status_code(response, "log in")
	if "登录失败" in response.text:
		print("用户名密码错误")
		print(response.text)
		exit(-1)


def get_checkin_info_() -> (str, str):
	global cookie_jar
	form_hash = ""
	sec_hash = ""
	header = {
		"User-Agent": user_agent,
		"Referer": referer
	}
	response = requests.get(get_checkin_url, headers=header, cookies=cookie_jar)
	cookie_jar.update(response.cookies)
	check_status_code(response, "get checkin info")
	if "您今天已经签到过了或者签到时间还未开始" in response.text:
		print("已签到")
		return "", ""
	if "您需要先登录才能继续本操作" in response.text:
		print("没登陆，请监察用户名密码")
		exit(-1)
	pattern = re.compile("formhash=([0-9a-z]+)")
	form_hashes = pattern.findall(response.text)
	if len(form_hashes) >= 1:
		form_hash = form_hashes[0]
	else:
		save_error(response, "formhash not found")
		exit(-1)
	pattern = re.compile('input name="sechash" type="hidden" value="([0-9a-zA-Z]+)"')
	sec_hashes = pattern.findall(response.text)
	if len(sec_hashes) >= 1:
		sec_hash = sec_hashes[0]
	else:
		save_error(response, "sec hash not found")
		sec_hash = "S00"
	return form_hash, sec_hash


def get_verify_code_(id_hash) -> str:
	global cookie_jar
	print("get verify code ...")
	header = {
		"User-Agent": user_agent,
		"Referer": referer
	}
	response = requests.get(get_verify_code_url % (id_hash, id_hash), headers=header, cookies=cookie_jar)
	cookie_jar.update(response.cookies)
	check_status_code(response, "get verify code phase 1 error")
	# misc.php?mod = seccode & update = 86288 & idhash = S0
	pattern = re.compile('src="([a-zA-Z0-9=&?.]+)"')
	srcs = pattern.findall(response.text)
	verify_code_url = ""
	if len(srcs) >= 1:
		verify_code_url = "https://www.1point3acres.com/bbs/" + srcs[0]
	else:
		print("response 中没有 验证码 的 url")
		print(response.text)
		exit(-1)
	response = requests.get(verify_code_url, headers=header, cookies=cookie_jar)
	cookie_jar.update(response.cookies)
	check_status_code(response, "get verify code phase 2 error")
	# print(len(response.content)) # 文件大小
	tmpfilename = "tmp.gif"
	if os.name == "posix":
		tmpfilename = "/tmp/" + tmpfilename
	file = open(tmpfilename, "wb")
	file.write(response.content)
	file.close()
	f = Image.open(tmpfilename)
	# f.show()
	return get_code_from_gif(f)


def check_verify_code_(id_hash, code):
	global cookie_jar
	print("check verify code...")

	header = {
		"User-Agent": user_agent,
		# "Referer": "https://www.1point3acres.com/bbs/dsu_paulsign-sign.html"
		"Referer": referer
	}
	response = requests.get(check_verify_code_url % (id_hash, code), headers=header, cookies=cookie_jar)
	cookie_jar.update(response.cookies)
	check_status_code(response, "check verify code phase 1 error")
	if "succeed" in response.text:
		print("verify code is right")
		return True
	if "invalid" in response.text:
		print("verify code is wrong")
		return False
	print("verify error")
	print(response.text)
	exit(-1)


def do_daily_checkin_(verify_code: str, form_hash: str, sec_hash: str = "S00") -> bool:
	global cookie_jar
	header = {
		"User-Agent": user_agent,
		"Content-Type": "application/x-www-form-urlencoded",
		"Referer": "https://www.1point3acres.com/bbs/dsu_paulsign-sign.html"
	}
	body = {
		"formhash": form_hash,
		"qdxq": "shuai",
		"qdmod": 2,
		"todaysay": None,
		"fastreply": 14,
		"sechash": sec_hash,
		"seccodeverify": verify_code
	}

	response = requests.post(post_checkin_url, headers=header, data=body, cookies=cookie_jar)
	check_status_code(response, "daily checkin")
	if "您需要先登录才能继续本操作" in response.text:  # cookie 出错
		print("login error，cookie missing")
		return False
	elif "您今日已经签到，请明天再来" in response.text:
		print("已签到")
		return True
	elif "验证码填写错误" in response.text:
		print("验证码错误")
		return False
	elif "做微信验证（网站右上角）后参与每日答题" in response.text:
		print("没绑微信")
		return True
	elif "恭喜你签到成功!获得随机奖励" in response.text:
		print("签到成功")
		return True
	else:
		save_error(response, "check in")
		return False


# 需要登录
def get_daily_task_answer() -> (str, str, str):
	global cookie_jar
	print("get question...")
	header = {
		"User-Agent": user_agent,
		"Referer": referer
	}
	response = requests.get(get_question_url, headers=header, cookies=cookie_jar)
	check_status_code(response, "get daily question")
	if "您今天已经参加过答题，明天再来吧！" in response.text:
		print("已答题")
		return "", "", ""
	cookie_jar.update(response.cookies)
	dom = xml.parseString(response.text)
	data = dom.childNodes[0].childNodes[0].data
	nodes = html.fragments_fromstring(data)
	form_hash_node = nodes[1].cssselect('form input[name="formhash"]')[0]
	form_hash = form_hash_node.get("value")
	sec_hash_node = nodes[1].cssselect("form input[name='sechash']")[0]
	sec_hash = sec_hash_node.get("value")
	print(f"form hash: {form_hash}")
	question_node = nodes[1].cssselect("form div span font")[0]
	question = question_node.text_content()
	question = question[5:]  # 去掉开始的 "【问题】 "
	question = question.strip()  # 去掉结尾空格
	print(f"question: {question}")
	answer_nodes = nodes[1].cssselect("form div.qs_option input")
	answers = {}
	for node in answer_nodes:
		id = node.get("value")
		text = node.getparent().text_content()
		answers[id] = text[2:]
	print(f"answers: {answers}")
	answer = ""
	answer_id = ""
	if question in questions.questions.keys():
		answer = questions.questions[question]

		if type(answer) == list:
			for k in answers:
				if answers[k] in answer:
					print(f"find answer: {answers[k]} option value: {k} ")
					answer_id = k
		else:
			for k in answers:
				if answers[k] == answer:
					print(f"find answer: {answers[k]} option value: {k} ")
					answer_id = k
	else:
		print("question not found")
	return answer_id, form_hash, sec_hash


def do_daily_question_(answer: str, verify_code: str, form_hash: str, sec_hash: str = "SA00") -> bool:
	global cookie_jar
	header = {
		"User-Agent": user_agent,
		"Referer": referer,
		"Content-Type": "application/x-www-form-urlencoded",
	}
	body = {
		"formhash": form_hash,
		"answer": answer,
		"sechash": sec_hash,
		"seccodeverify": verify_code,
		"submit": "true"
	}
	print(body)
	# 网站的原版请求是 multipart/form-data ，但是我发现用 application/x-www-form-urlencoded 也是可以的
	# response = requests.post(post_answer_url, files=body, headers=header, cookies=cookie_jar)
	response = requests.post(post_answer_url, data=body, headers=header, cookies=cookie_jar)
	check_status_code(response, "post answer")
	if "抱歉，您的请求来路不正确或表单验证串不符，无法提交" in response.text:
		print("抱歉，您的请求来路不正确或表单验证串不符，无法提交")
		return False
	elif "抱歉，验证码填写错误" in response.text:
		print("验证码错误")
		return False
	elif "登录后方可进入应用" in response.text:
		print("cookie 错误")
		return False
	elif "恭喜你，回答正确" in response.text:
		print("答题成功")
		return True
	else:
		save_error(response, "post answer")
		return False
