import webapp2
import cgi
import jinja2
import os
import operator
from google.appengine.api import users
from google.appengine.ext import db

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

class MainPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()                    
        if user:
            logout_url = users.create_logout_url(self.request.uri)
            template = jinja_environment.get_template('index.html')
            self.response.out.write(template.render({'logout_url':logout_url}))
        else:
            self.redirect(users.create_login_url(self.request.uri))


class PredictPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            template = jinja_environment.get_template('predictpage.html')
            self.response.out.write(template.render({}))
        else:
            self.redirect(users.create_login_url(self.request.uri))

class SavePrediction(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        admin_pass = cgi.escape(self.request.get('password'))
        if admin_pass=="phool":
            admin = 1
        else:
            admin = 0
        match = int(cgi.escape(self.request.get('match')))
        home_score = int(cgi.escape(self.request.get('home_score')))
        away_score = int(cgi.escape(self.request.get('away_score')))
        home_scorers = cgi.escape(self.request.get('home_scorers'))
        home_scorers_str = home_scorers.split(',')
        home_scorers = []
        for scorer in home_scorers_str:
            if scorer.isnumeric():
                home_scorers.append(int(scorer))
        
        away_scorers = cgi.escape(self.request.get('away_scorers'))
        away_scorers_str = away_scorers.split(',')
        away_scorers = []
        for away_scorer in away_scorers_str:
            if away_scorer.isnumeric():
                away_scorers.append(int(away_scorer))
        
        self.response.out.write("Match:"+str(match)+"<br>")
        self.response.out.write("Home Score:"+str(home_score)+"<br>")
        self.response.out.write("Home Scorers:"+str(home_scorers)+"<br>")
        self.response.out.write("Away Score:"+str(away_score)+"<br>")
        self.response.out.write("Away Scorers:"+str(away_scorers)+"<br>")
        
        pred = db.GqlQuery("SELECT * "
                                "FROM Prediction "
                                "WHERE ANCESTOR IS :1 "
                                "AND user = :2 "
                                "AND match = :3",
                                prediction_key(),
                                user,
                                match)
        if pred.get():
            prediction = pred.get()
        else:       
            prediction = Prediction(parent=prediction_key())
        prediction.user = user
        prediction.match = match
        prediction.home_score = home_score
        prediction.home_scorers = home_scorers
        prediction.away_score = away_score
        prediction.away_scorers = away_scorers
        prediction.admin = admin
        prediction.put()
        self.response.out.write("SAVED..")
        if admin:
            distributePoints(prediction)
        self.redirect('/predict')
        
def distributePoints(result):
    predictions = db.GqlQuery("SELECT * "
                                "FROM Prediction "
                                "WHERE ANCESTOR IS :1 "
                                "AND match = :2",
                                prediction_key(),
                                result.match)
        
    for prediction in predictions:
        points = 0
        points = points + checkWinner(result, prediction)
        points = points + checkScore(result, prediction)
        points = points + checkGd(result, prediction)
        points = points + checkScorers(result, prediction)
        if(prediction.match>24):
            if(prediction.match>28):
                if(prediction.match==31):
                    points = points*4
                else:
                    points = points*3
            else:
                points = points*2
        prediction.points = points
        prediction.put()

def checkWinner(result,prediction):
    
    #HOME WIN
    if (result.home_score - result.away_score)>0:
        if(prediction.home_score - prediction.away_score)>0:
            return 2
        elif(prediction.home_score - prediction.away_score)==0:
            return 0
        else:
            return -2
        
    #DRAW
    elif (result.home_score - result.away_score)==0:
        if(prediction.home_score - prediction.away_score)==0:
            return 2
        else:
            return 0 
        
    #AWAY WIN
    if (result.home_score - result.away_score)<0:
        if(prediction.home_score - prediction.away_score)<0:
            return 2
        elif(prediction.home_score - prediction.away_score)==0:
            return 0
        else:
            return -2
        
def checkGd(result, prediction):
    if (result.home_score - result.away_score)==(prediction.home_score - prediction.away_score):
        return 1
    else:
        return 0

def checkScore(result, prediction):
    if checkGd(result, prediction):
        if result.home_score==prediction.home_score:
            return 2
        else:
            return 0
    else:
        return 0

def checkScorers(result, prediction):
    points = 0
    home = result.home_scorers
    away = result.away_scorers
    
    home_p = prediction.home_scorers
    away_p = prediction.away_scorers
    
    for scorer in home_p:
        points = points + home.count(scorer)
    
    for scorer in away_p:
        points = points + away.count(scorer)
    
    return points        
                
class ViewPredict(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        predictions = db.GqlQuery("SELECT * "
                                "FROM Prediction "
                                "WHERE ANCESTOR IS :1 "
                                "AND user = :2 "
                                "ORDER BY match",
                                prediction_key(),
                                user)
        template = jinja_environment.get_template('viewPredicts.html')
        self.response.out.write(template.render({'predictions':predictions}))

class ViewResults(webapp2.RequestHandler):
    def get(self):
        predictions = db.GqlQuery("SELECT * "
                                "FROM Prediction "
                                "WHERE ANCESTOR IS :1 "
                                "AND admin = :2 "
                                "ORDER BY match",
                                prediction_key(),
                                1)
        template = jinja_environment.get_template('viewResults.html')
        self.response.out.write(template.render({'predictions':predictions}))

class ViewLeaders(webapp2.RequestHandler):
    def get(self):
        predictions = db.GqlQuery("SELECT * "
                                    "FROM Prediction "
                                    "WHERE ANCESTOR IS :1 "
                                    "AND admin = :2 ",
                                    prediction_key(),
                                    0)        
        user_scores = {}
            
        for prediction in predictions:
            score = 0
            if prediction.points is not None:
                score = user_scores.get(prediction.user.nickname())
                if score is not None:
                    score = score + prediction.points
                    user_scores[prediction.user.nickname()] = score
                else:
                    user_scores[prediction.user.nickname()] = prediction.points
        
        user_scores = sorted(user_scores.iteritems(), key=operator.itemgetter(1), reverse=True)
        
        template = jinja_environment.get_template('viewLeaders.html')
        self.response.out.write(template.render({'scores':user_scores}))

class Prediction(db.Model):
    user = db.UserProperty()
    match = db.IntegerProperty()
    home_score = db.IntegerProperty()
    home_scorers = db.ListProperty(int) 
    away_score = db.IntegerProperty()
    away_scorers = db.ListProperty(int) 
    admin = db.IntegerProperty()
    points = db.IntegerProperty(required=False)
    
def prediction_key():
    return db.Key.from_path('Prediction', "EURO 2012")
    
app = webapp2.WSGIApplication([('/', MainPage),
                              ('/predict',PredictPage),
                              ('/viewPredictions',ViewPredict),
                              ('/savePredict',SavePrediction),
                              ('/viewResults',ViewResults),
                              ('/viewLeaders',ViewLeaders)],                              
                              debug=True)

