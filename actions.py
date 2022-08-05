from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from rasa_sdk import Action
from rasa_sdk.events import SlotSet
import pandas as pd

import re
from threading import Thread
from flask import Flask
from flask_mail import Mail, Message
from time import sleep

from concurrent.futures import ThreadPoolExecutor

ZomatoData = pd.read_csv('zomato.csv', encoding='latin1')
ZomatoData = ZomatoData.drop_duplicates().reset_index(drop=True)
top_restaurant_details = []

operational_cities = ['ahmedabad', 'bangalore', 'chennai', 'delhi', 'hyderabad', 'kolkata', 'mumbai', 'pune','agra', 'ajmer', 'aligarh', 'amravati', 'amritsar', 'asansol', 'aurangabad', 'bareilly',
                       'belgaum',
                       'bhavnagar', 'bhiwandi', 'bhopal', 'bhubaneswar', 'bikaner', 'bilaspur', 'bokaro steel city',
                       'chandigarh',
                       'coimbatore', 'cuttack', 'dehradun', 'dhanbad', 'bhilai', 'durgapur', 'erode', 'faridabad',
                       'firozabad',
                       'ghaziabad', 'gorakhpur', 'gulbarga', 'guntur', 'gwalior', 'gurgaon', 'guwahati', 'hamirpur',
                       'hubli–dharwad',
                       'indore', 'jabalpur', 'jaipur', 'jalandhar', 'jammu', 'jamnagar', 'jamshedpur', 'jhansi',
                       'jodhpur',
                       'kakinada', 'kannur', 'kanpur', 'kochi', 'kolhapur', 'kollam', 'kozhikode', 'kurnool',
                       'ludhiana', 'lucknow',
                       'madurai', 'malappuram', 'mathura', 'goa', 'mangalore', 'meerut', 'moradabad', 'mysore',
                       'nagpur', 'nanded',
                       'nashik', 'nellore', 'noida', 'patna', 'pondicherry', 'purulia', 'prayagraj', 'raipur', 'rajkot',
                       'rajahmundry', 'ranchi', 'rourkela', 'salem', 'sangli', 'shimla', 'siliguri', 'solapur',
                       'srinagar', 'surat',
                       'thiruvananthapuram', 'thrissur', 'tiruchirappalli', 'tiruppur', 'ujjain', 'bijapur', 'vadodara',
                       'varanasi',
                       'vasai-virar city', 'vijayawada', 'visakhapatnam', 'vellore', 'warangal']


def RestaurantSearch(City, Cuisine):
    TEMP = ZomatoData[(ZomatoData['Cuisines'].apply(lambda x: Cuisine.lower() in x.lower())) & (
        ZomatoData['City'].apply(lambda x: City.lower() in x.lower()))]
    return TEMP[['Restaurant Name', 'Address', 'Average Cost for two', 'Aggregate rating']]


def validate_location(loc):
    return loc.lower() in operational_cities


class ActionSearchRestaurants(Action):
    def name(self):
        return 'action_search_restaurants'

    def run(self, dispatcher, tracker, domain):
        loc = tracker.get_slot('location')
        print("Location is::" + loc)
        print("is valid Location:" + str(validate_location(loc)))
        if not (validate_location(loc)):
            dispatcher.utter_message("Sorry, we do not operate in " + loc + " yet. Please try some other city.")
            return []
        cuisine = tracker.get_slot('cuisine')
        budget_min_price = int(tracker.get_slot('budgetmin'))
        budget_max_price = int(tracker.get_slot('budgetmax'))
        results = RestaurantSearch(City=loc, Cuisine=cuisine)
        response = ""
        restaurant_exist = False
        if results.shape[0] == 0:
            dispatcher.utter_message("Sorry, no results found :(" + "\n")
            restaurant_exist = False
            return [SlotSet('location', loc), SlotSet('restaurant_exist', restaurant_exist)]
        else:
            results = find_restaurant_in_budget_price(results, budget_min_price, budget_max_price)
            if len(results) == 0:
                dispatcher.utter_message("Sorry, no results found :(" + "\n")
                restaurant_exist = False
                return [SlotSet('location', loc), SlotSet('restaurant_exist', restaurant_exist)]

            for restaurant in results.iloc[:5].iterrows():
                restaurant = restaurant[1]
                response = response + F"Found {restaurant['Restaurant Name']} in {restaurant['Address']} rated {restaurant['Aggregate rating']} with avg cost {restaurant['Average Cost for two']} \n\n"

            dispatcher.utter_message("Top 5 Restaurant : " + "\n" + response)
            global top_restaurant_details
            top_restaurant_details = results[:10]
            if len(top_restaurant_details) > 0:
                restaurant_exist = True
        return [SlotSet('location', loc), SlotSet('restaurant_exist', restaurant_exist)]


def find_restaurant_in_budget_price(dataset, min_value, max_value) -> object:
    dataset = dataset[(dataset['Average Cost for two'] > min_value) & (dataset['Average Cost for two'] < max_value)]
    dataset = dataset.sort_values(by=['Aggregate rating'], ascending=False)
    return dataset


class ActionValidateEmail(Action):
    def name(self):
        return 'action_validate_email'

    def run(self, dispatcher, tracker, domain):
        pattern = "(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
        email_check = tracker.get_slot('email')
        if email_check is not None:
            if re.search("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email_check):
                return [SlotSet('email_ok', True)]
            else:
                dispatcher.utter_message("Sorry this is not a valid email. please check for typing errors")
                return [SlotSet('email', None), SlotSet("email_ok", False)]
        else:
            dispatcher.utter_message("Sorry I could'nt understand the email address you provided? Please provide again")
            return [SlotSet('email', None)]


def config():
    gmail_user = "hungertames@gmail.com"
    gmail_pwd = "bh00khaH00nM@!n"
    gmail_config = (gmail_user, gmail_pwd)
    return gmail_config


def mail_config(gmail_credential_detail):
    mail_settings = {

        "MAIL_SERVER": 'smtp.gmail.com',
        "MAIL_PORT": 465,
        "MAIL_USE_TLS": False,
        "MAIL_USE_SSL": True,
        "MAIL_USERNAME": gmail_credential_detail[0],
        "MAIL_PASSWORD": gmail_credential_detail[1],

    }
    return mail_settings


gmail_credentials = config()

app = Flask(__name__)
app.config.update(mail_config(gmail_credentials))
mail = Mail(app)


def send_async_email(flask_app, msg):
    with flask_app.app_context():
        # block only for testing parallel thread
        for i in range(10, -1, -1):
            sleep(2)
        mail.send(msg)


def send_email(recipient, top_10_restaurant_df):
    msg = Message(subject="Restaurant Details", sender=gmail_credentials[0], recipients=[recipient])
    msg.html = u'<h2>Foodie has found few restaurants for you:</h2>'

    for ind, val in top_10_restaurant_df.iterrows():
        name = top_10_restaurant_df['Restaurant Name'][ind]
        location = top_10_restaurant_df['Address'][ind]
        budget = top_10_restaurant_df['Average Cost for two'][ind]
        rating = top_10_restaurant_df['Aggregate rating'][ind]

        msg.html += u'<h3>{name} (Rating: {rating})</h3>'.format(name=name, rating=rating)
        msg.html += u'<h4>Address: {locality}</h4>'.format(locality=location)
        msg.html += u'<h4>Average Budget for 2 people: Rs{budget}</h4>'.format(budget=str(budget))

    print(msg.html)
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()


class ActionValidateLocation(Action):

    def name(self):
        return "action_validate_location"

    def run(self, dispatcher, tracker, domain):
        loc = tracker.get_slot('location')
        print("Location is::"+loc)
        print("is valid Location:" + str(validate_location(loc)))
        if not (validate_location(loc)):
            dispatcher.utter_message("Sorry, we do not operate in " + loc + " yet. Please try some other city.")
            return [SlotSet('location', None), SlotSet("location_ok", False)]
        else:
            return [SlotSet('location', loc), SlotSet("location_ok", True)]


class ActionSendMail(Action):
    def name(self):
        return 'action_send_mail'

    def run(self, dispatcher, tracker, domain):
        recipient = tracker.get_slot('email')

        try:
            restaurant_top_10_details = top_restaurant_details.copy()
            send_email(recipient, restaurant_top_10_details)
            dispatcher.utter_message("Have a great day! Mail is sent")
        except:
            dispatcher.utter_message("Email not sent, "
                                     ""
                                     ""
                                     "address is not valid")


class ActionValidateBudget(Action):
    def name(self):
        return 'action_validate_budget'

    def run(self, dispatcher, tracker, domain):
        error_msg = "Sorry!! price range not supported, please re-enter."
        try:
            budgetmin = int(tracker.get_slot('budgetmin'))
            budgetmax = int(tracker.get_slot('budgetmax'))
        except ValueError:
            dispatcher.utter_message(error_msg)
            return [SlotSet('budgetmin', None), SlotSet('budgetmax', None), SlotSet('budget_ok', False)]
        min_dict = [0, 300, 700]
        max_dict = [300, 700]
        if budgetmin in min_dict and (budgetmax in max_dict or budgetmax > 700):
            return [SlotSet('budgetmin', budgetmin), SlotSet('budgetmax', budgetmax), SlotSet('budget_ok', True)]
        else:
            dispatcher.utter_message(error_msg)
            return [SlotSet('budgetmin', 0), SlotSet('budgetmax', 10000), SlotSet('budget_ok', False)]


class ActionRestarted(Action):
    def name(self):
        return 'action_restart'

    def run(self, dispatcher, tracker, domain):
        return [Restarted()]


class ActionSlotReset(Action):
    def name(self):
        return 'action_slot_reset'

    def run(self, dispatcher, tracker, domain):
        return [AllSlotsReset()]
