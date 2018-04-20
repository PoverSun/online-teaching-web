# -*- coding: utf-8 -*-
import json
from tornado.gen import coroutine
import logging
from datetime import datetime
from geetest import GeetestLib
from handlers.common_handlers.base_handler import BaseHandler
from libs.motor.base import BaseMotor
from models.bulletin import Bulletin_info
from models.files import Files_info
from config import GT_ID,GT_KEY,MongoBasicInfoDb,STUDENTS,FRONT_USER
from utils.hashers import make_password
from utils.xdemail import send_email
from utils.captcha import get_captcha
#首页
class IndexHandler(BaseHandler):
    def get(self):
        bulletin_coll = Bulletin_info()
        top_bulletin = bulletin_coll.by_top_limit2
        bulletins_untop = bulletin_coll.by_untop_limit2
        email = self.get_session('current_email')
        name = self.get_session("username") if self.get_session("username") else ''
        role = self.get_session('role') if self.get_session('role') else ''
        args = {
            'bulletins_top':top_bulletin,
            'username': name,
            'role':role,
            'bulletins_untop':bulletins_untop
        }
        self.render("front/front_index.html",**args)

#----------------------------------------------------------登录
class SignInHandler(BaseHandler):
    @coroutine
    def get(self):
        self.set_cookie('_xsrf', self.xsrf_token)
        msg = ''
        action_url = '/signin'
        self.render("front/front_signin.html",msg=msg,action_url=action_url)

    @coroutine
    def post(self):
        try:
            gt = GeetestLib(GT_ID, GT_KEY)
            challenge = self.get_argument(gt.FN_CHALLENGE, "")
            validate = self.get_argument(gt.FN_VALIDATE, "")
            seccode = self.get_argument(gt.FN_SECCODE, "")
            status = int(self.session[gt.GT_STATUS_SESSION_KEY])
            user_id = self.session["user_id"]
            if status:
                verify_res = gt.success_validate(challenge, validate, seccode, user_id)
            else:
                verify_res = gt.failback_validate(challenge, validate, seccode)
                self.session["user_id"] = user_id
            if verify_res:
                email = self.get_argument("email")
                password = self.get_argument("password")
                if email and password:
                    password = make_password(password)

                    front_user_coll = BaseMotor().client[MongoBasicInfoDb][FRONT_USER]
                    # stu_doc = yield student_coll.find_one({"_id": email})
                    front_user_doc = yield front_user_coll.find_one({"email": email})

                    if not front_user_doc:
                        msg = '账户不存在，请重新输入或前往注册！'
                        self.render("front/front_signin.html", msg=msg,action_url = '/signin')
                    else:
                        pwd = front_user_doc['password']
                        if password == pwd:
                            self.session['current_email'] = email
                            self.session['role'] = front_user_doc['role']
                            self.session['username'] = front_user_doc['username']
                            self.redirect("/")
                        else:
                            msg = '密码错误，请重新输入！'
                            self.render("front/front_signin.html", msg=msg, action_url='/signin')

                else:
                    msg = '邮箱或密码值获取错误，请重新输入！'
                    self.render("front/front_signin.html", msg=msg ,action_url = '/signin')
            else:
                msg = '验证码验证失败，请重新验证！'
                self.render("front/front_signin.html",msg=msg ,action_url = '/signin')
        except Exception as e:
            print e
            logging.exception(e)
            self.render("front/front_signin.html", msg=e,action_url = '/signin')
#----------------------------------------------------------注册
class FrontRegistHandler(BaseHandler):
    @coroutine
    def get(self):
        msg=''
        action_url = '/regist'
        self.render("front/front_regist.html",msg=msg,action_url=action_url)

    @coroutine
    def post(self):
        post_data = self.request.body
        try:
            post_data = json.loads(post_data)
        except (TypeError, ValueError):
            self.write_response({}, 0, '参数格式错误')
            return
        try:
            action = post_data.get("action",None)
            if not action:
                self.write_response({},0,_err='没有相应的操作方法！')
            elif action == 'send_email':
                email = post_data.get("email", None)
                if email:
                    subject = '计算机组成与结构教学网站邮箱注册服务验证！'
                    captcha = get_captcha(4)
                    self.conn.set("email_captcha",captcha)
                    body = "温馨提示：尊敬的用户，您好！我们的工作人员是不会向您索要邮箱验证码，请务将验证码告诉他人，以免您的账户信息泄漏！\n您的邮箱验证码是：【"+captcha+"】10分钟内有效！"
                    try:
                        message = send_email(self,subject=subject,body=body,to_email=email)
                        has_send = self.get_session('has_send_email')
                        if not has_send:
                            self.session['has_send_email'] = email
                            message.send()
                        self.write_response({})
                        # else:
                        #     self.render("front/front_regist.html", msg='邮件已发送成功,请前往邮箱进行验证！', action_url='/regist')
                    except Exception as e:
                        print e
                        self.render("front/front_regist.html", msg=e, action_url='/regist')
                else:
                    self.render("front/front_regist.html", msg='邮箱帐号异常！', action_url='/regist')
            elif action == 'regist':
                email = post_data.get("email",None)
                password = post_data.get("password",None)
                captcha = post_data.get("captcha",None)
                if not (email and password and captcha):
                    self.write_response({},0,_err='值获取错误！')
                cache_captcha = self.conn.get("email_captcha")
                if cache_captcha.lower() == captcha:
                    password = make_password(password)
                    try:
                        user_coll = BaseMotor().client[MongoBasicInfoDb][FRONT_USER]
                        user_doc = yield user_coll.find_one({"_id": email})
                        if not user_doc:
                            try:
                                document = {
                                    '_id':email,
                                    'is_stu': False,
                                    'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'update_time': '',
                                    'is_active': True,
                                    'email': email,
                                    'role': '用户',
                                    'permission':'user',
                                    'password': password,
                                }
                                res = user_coll.insert(document)
                                if not res:
                                    self.write_response({},0,_err='更新数据库出错！')
                                else:
                                    self.write_response({})
                            except Exception as e:
                                print e
                                self.render("front/front_regist.html", msg=e, action_url='/regist')
                        else:
                            self.render("front/front_regist.html", msg='账户已存在，请直接登录！', action_url='/regist')
                    except Exception as e:
                        print e
                        self.write_response({},0,_err='数据库连接异常！')
                else:
                    self.render("front/front_regist.html", msg='验证码输入不一致！', action_url='/regist')
        except Exception as e:
            print e
            self.write_response({},0)




#----------------------------------------------------------忘记密码
class ForgetPwdHandler(BaseHandler):

    @coroutine
    def get(self):
        msg=''
        action_url = '/forgetpwd'
        context = {
            'msg':msg,
            'action_url':action_url
        }
        self.render("front/front_forgetpwd.html",**context)

    @coroutine
    def post(self):
        post_data = self.request.body
        try:
            post_data = json.loads(post_data)
        except (TypeError, ValueError):
            self.write_response({}, 0, '参数格式错误')
            return
        try:
            action = post_data.get("action",None)
            if not action:
                self.write_response({},0,_err='没有相应的操作方法！')
            elif action == 'retrieve_password':
                email = post_data.get("email", None)
                if email:
                    subject = '计算机组成与结构教学网站邮箱找回密码服务验证！'
                    captcha = get_captcha(4)
                    self.conn.set("email_captcha", captcha)
                    body = "温馨提示：尊敬的用户，您好！我们的工作人员是不会向您索要邮箱验证码，请务将验证码告诉他人，以免您的账户信息泄漏！\n您的邮箱验证码是：【" + captcha + "】10分钟内有效！"
                    try:
                        message = send_email(self, subject=subject, body=body, to_email=email)
                        has_send = self.get_session('has_send_email')
                        if not has_send:
                            self.session['has_send_email'] = email
                            message.send()
                        self.write_response({})
                    except Exception as e:
                        print e
                        self.render("front/front_forgetpwd.html", msg=e, action_url='/forgetpwd')
                else:
                    self.render("front/front_forgetpwd.html", msg='邮箱帐号异常！', action_url='/forgetpwd')

            elif action == 'verify':
                email = post_data.get("email", None)
                captcha = post_data.get("captcha",None)
                cache_captcha = self.conn.get("email_captcha")
                if not (cache_captcha and captcha):
                    self.write_response({},0,'缺少邮箱验证码信息！')
                    return
                if not email:
                    self.write_response({},0,'缺少邮箱帐号信息！')
                    return
                try:
                    front_user_coll = BaseMotor().client[MongoBasicInfoDb][FRONT_USER]
                    front_user_doc = front_user_coll.find_one({'email':email})
                    if not front_user_doc:
                        self.write_response({},0,'此邮箱账户未注册使用！')
                        return
                    else:
                        if cache_captcha.lower() == captcha.lower():
                            self.write_response({})
                            return
                        else:
                            self.write_response({},0,'邮箱验证码错误！')
                            return
                except Exception as e:
                    logging.exception(e)


            elif action == 'save':
                email = post_data.get("email", None)
                password = post_data.get("password", None)
                repeat_password = post_data.get("repeat_password",None)
                if not email:
                    self.write_response({},0,'缺少邮箱帐号信息！')
                    return
                if not (password and repeat_password):
                    self.write_response({},0,'密码获取错误！')
                    return
                try:
                    front_user_coll = BaseMotor().client[MongoBasicInfoDb][FRONT_USER]
                    front_user_doc = front_user_coll.find_one({'email':email})
                    if not front_user_doc:
                        self.write_response({},0,'此邮箱账户未注册使用！')
                        return
                    else:
                        if password == repeat_password:
                            res = front_user_coll.update_one({'email':email},{
                                '$set':{
                                    '{0}'.format('password'):make_password(password)
                                }
                            })
                            if res:
                                self.write_response({})
                            else:
                                self.write_response({},0,'密码找回失败！')
                        else:
                            self.write_response({},0,'两次密码输入不一致！')
                            return
                except Exception as e:
                    logging.exception(e)
            else:
                pass
        except Exception as e:
            logging.exception(e)
            print e



class SignupHandler(BaseHandler):
    @coroutine
    def get(self):
        try:
            self.clear_all_cookies()
            self.session['current_email'] = ''
            self.session['role'] = ''
            self.session['username'] = ''
        except Exception as e:
            logging.exception(e)
            print e
        self.redirect('/signin')

class testHandler(BaseHandler):
    def get(self):
        try:
            email = 'x15729557664@163.com'
            host = self.request.host
            url = self.request.uri
            subject = 'www.baidu.com'
            body = host+url
            # message =send_email()
            self.write(body)
        except Exception as e:
            print e



#----------------------------------------------------------课程中心
class courseIntroHandler(BaseHandler):
    @coroutine
    def get(self):
        email = self.get_session('current_email')
        name = self.get_session("username") if self.get_session("username") else ''
        role = self.get_session('role') if self.get_session('role') else ''
        args = {
            'user': email,
            'role': role,
            'username':name
        }
        self.render("front/course_introduction.html", **args)


class courseTeachersHandler(BaseHandler):
    @coroutine
    def get(self):
        email = self.get_session('current_email')
        name = self.get_session("username") if self.get_session("username") else ''
        role = self.get_session('role') if self.get_session('role') else ''
        args = {
            'user': email,
            'role': role,
            'username':name
        }
        self.render("front/course_teachers.html", **args)

class courseDevelopHandler(BaseHandler):
    @coroutine
    def get(self):
        email = self.get_session('current_email')
        name = self.get_session("username") if self.get_session("username") else ''
        role = self.get_session('role') if self.get_session('role') else ''
        args = {
            'user': email,
            'role': role,
            'username':name
        }
        self.render("front/course_develop.html", **args)

#----------------------------------------------------------课程中心


#----------------------------------------------------------公告
#公告页面
class frontBulletinsHandler(BaseHandler):
    @coroutine
    def get(self):
        email = self.get_session('current_email')
        name = self.get_session("username") if self.get_session("username") else ''
        role = self.get_session('role') if self.get_session('role') else ''
        bulletin_coll = Bulletin_info()
        top_list = bulletin_coll.by_top_sort
        untop_list = bulletin_coll.by_untop_sort
        args = {
            'user':'',
            'role': role,
            'bulletin_infos':top_list,
            'unTopBulletins':untop_list,
            'username':name
        }
        if email:
            args['user'] = email
        self.render("front/front_bulletin.html", **args)


#公告详情页面
class bulletinDetailHandler(BaseHandler):
    @coroutine
    def get(self):
        email = self.get_session('current_email') if self.get_session('current_email') else ''
        name = self.get_session("username") if self.get_session("username") else ''
        role = self.get_session('role') if self.get_session('role') else ''
        id = self.get_argument('id',None)
        if not id:
            self.write_response({},0,'公告id获取错误！')
            return
        try:
            bulletin_coll = Bulletin_info(id=id)
            bulletin = bulletin_coll.by_id
            is_top = bulletin['is_top']
            if is_top == True:
                is_top = 1
            else:
                is_top = ''
            args = {
                'user': email,
                'role': role,
                'bulletin':bulletin,
                'is_top':is_top,
                'username':name
            }
            self.render("front/front_bulletin_detail.html", **args)
        except Exception as e:
            logging.exception(e)


#----------------------------------------------------------公告

#----------------------------------------------------------资料下载页面

class fileDownLoadPageHandle(BaseHandler):
    @coroutine
    def get(self):
        email = self.get_session('current_email') if self.get_session('current_email') else ''
        name = self.get_session("username") if self.get_session("username") else ''
        role = self.get_session('role') if self.get_session('role') else ''
        try:
            args = {
                'user': email,
                'role': role,
                'username':name
            }
            self.render("front/front_file.html", **args)
        except Exception as e:
            logging.exception(e)

class fileDownLoadInfoHandler(BaseHandler):
    @coroutine
    def get(self):
        try:
            file = Files_info()
            file_list = file.by_is_active
            if file_list:
                self.write_response(file_list)
            else:
                self.write_response({})
                return
        except Exception as e:
            logging.exception(e)
            self.write_response({},0,'资料查询出错！')

            #----------------------------------------------------------资料下载页面

# 获取排序后的数据
class getSortLimitFileHandler(BaseHandler):
    @coroutine
    def get(self):
        try:
            file = Files_info()
            if not file:
                self.write_response({})
                return
            else:
                file_list = file.by_is_active_sort
            if file_list:
                self.write_response(file_list)
            else:
                self.write_response({})
                return
        except Exception as e:
            logging.exception(e)
            self.write_response({}, 0, '资料查询出错！')