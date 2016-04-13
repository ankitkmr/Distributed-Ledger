import random
import urllib
import urllib2
import json

from flask import Flask, session, render_template, request, url_for, redirect
from flaskext.mysql import MySQL
from flask.ext.wtf import Form

from wtforms import StringField, SubmitField, PasswordField, SelectField, DecimalField 
from wtforms.validators import Required

app = Flask(__name__)

nodes = {1:"http://172.24.65.29:5000",2:"http://10.211.55.4:5000",3:"http://10.211.55.3:5000"}

nodeID = 1
NodeKey = 'node1pass'

# Sessions variables are stored client side, on the users browser the content of the variables is encrypted, so users can't
# actually see it. They could edit it, but again, as the content wouldn't be signed with this hash key, it wouldn't be valid
# You need to set a secret key (random text) and keep it secret
app.config['SECRET_KEY']='DBMSProject'

mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'blockchain'
app.config['MYSQL_DATABASE_DB'] = 'blockchain'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
mysql.init_app(app)

class SignupForm(Form):
	name = StringField('What is your Name?',validators=[Required()])
	password = PasswordField('Select a Password',validators=[Required()])
	signup = SubmitField('Sign Up')

class LoginForm(Form):
	walletID = StringField('Enter your Wallet ID', validators=[Required()])
	password = PasswordField('Enter your Password', validators=[Required()])
	submit = SubmitField("Login")

class WalletForm(Form):
	receiverID = StringField("Enter Receiver's Wallet ID", validators=[Required()])
	amount = DecimalField("Enter Amount to Send", validators=[Required()])
	password = PasswordField('Enter your Password', validators=[Required()])
	send = SubmitField("Send Money")

class LogOutForm(Form):
	logout = SubmitField("Log Out")

class RefreshForm(Form):
	refresh = SubmitField("Refresh Status")


@app.route('/consent',methods=['POST'])
def consent():
	conn = mysql.connect()
	cursor = conn.cursor()

	NID = request.form['NID']
	NPass = request.form['nodekey']

	cursor.execute("Select nodeID from nodes where nodeID =%s and nodekey=%s",(NID,NPass))
	tmpFlag = cursor.fetchone()

	if tmpFlag is None:
		return "Invalid Access"

	OID = int(request.form['OID'])
	print 'Received Request from',NID, 'for Process', str(OID)


	if OID ==1: #Get highest wallet ID number along with its other data
		cursor.execute("SELECT * from wallet order by walletID desc;")
		return json.dumps(cursor.fetchone())

	elif OID ==2: #Get current Amount and TransactionRank
		cursor.execute("SELECT Amount, transactionRank from wallet where walletID = %s;",(request.form['walletID'][7:]))
		return json.dumps(cursor.fetchone())

	elif OID ==3:#Register A new Wallet and Set Login status Yes
		cursor.execute("insert into wallet(walletID,name,amount,password,status) values (%s,%s,%s,%s,'yes');",( request.form['walletID'][7:],
																	 request.form['name'], request.form['amount'],request.form['password']))
		conn.commit()
		return 'OK'

	elif OID ==4: # Check for walletID, password combo in case it failed to register due to Network Packet Loss/ Node Failure in current Node
		cursor.execute("SELECT * from wallet where walletID = %s and password= %s;",(request.form['walletID'][7:],request.form['password']))
		return json.dumps(cursor.fetchone())

	elif OID ==5:	#Set login status to yes for current walletID
		cursor.execute("Select status from wallet where walletID=%s;",(request.form['walletID'][7:]))
		if cursor.fetchone()[0]=='yes':
			#Already Logged In to that node but failed to register to current node maybe due to Packet Loss
			return '120' #Code for already Logged In

		cursor.execute("update wallet set status='yes' where walletID = %s;",(request.form['walletID'][7:]))
		conn.commit()
		return 'OK'

	elif OID ==6: #Check to see if Transactions are up-to date with latest transactions regarding current walletID on any Node
		cursor.execute("Select * from transactions where senderID=%s and transactionID>%s order by transactionID desc;",(request.form['walletID'][7:],request.form['lastTransID']))
		return json.dumps(cursor.fetchall())

	elif OID ==7: #Log out for current walletID, Ensure Single point Access
		cursor.execute("update wallet set status='no' where walletID = %s;",(request.form['walletID'][7:]))
		conn.commit()
		return 'OK'

	elif OID==8: #Check if receiver walletID exists on some node and hasn't been updated on current Node
		cursor.execute("Select walletID from wallet where walletID = %s;", (request.form['receiverID'][7:]))
		return json.dumps(cursor.fetchone())

	elif OID ==9: #Check to see if Transactions are up-to date with latest transactions on any Node
		cursor.execute("Select * from transactions where transactionID>%s order by transactionID desc;",(request.form['lastTransID']))
		return json.dumps(cursor.fetchall())

	elif OID==10: #Check for latest transactionID on any node to generate next transactionID
		cursor.execute("Select transactionID from transactions order by transactionID desc;")
		return json.dumps(cursor.fetchone())

	elif OID==11:	#Make the transaction object in every node, update relevant accounts everywhere
					#Also update transactionRank on relevant wallets 
		cursor.execute("Insert into transactions(transactionID, senderID, receiverID, Amount) values (%s,%s,%s,%s);",(request.form['transactionID'],
										request.form['walletID'][7:],request.form['receiverID'][7:],request.form['amount']))

		cursor.execute("update wallet set Amount = Amount - %s, transactionRank=transactionRank+1 where walletID = %s;",(
											request.form['amount'], request.form['walletID'][7:]))
		
		cursor.execute("update wallet set Amount = Amount + %s,transactionRank=transactionRank+1 where walletID = %s;",(
										request.form['amount'], request.form['receiverID'][7:]))
		conn.commit()
		return 'OK'

	elif OID==12:#Rollback
		if 'op1' in request.form:
			#Transaction Rollback
			try:
				cursor.execute(request.form['op1'])
				cursor.execute(request.form['op2'])
				cursor.execute(request.form['op3'])
				conn.commit()
				return 'OK'
			except:
				return 'Fail'
		else:
			try:
				cursor.execute(request.form['rollback'])
				conn.commit()
				return 'OK'
			except:
				return 'Fail'

	else:
		return 'Invalid Operation'



def paxos(NID, dict_data):
	try:
		url = nodes[NID] + '/consent'
		data = urllib.urlencode(dict_data)
		req = urllib2.Request(url, data)
		response = urllib2.urlopen(req)
		return response.read()
	except:
		return "Fail"

@app.route('/')
def index():
	return render_template('index.html')


@app.route('/SignUp',methods=["GET","POST"])
def signup():
	form = SignupForm()
	
	try:
		# Trying to access walletID field in session object to check if a current session exists, 
		# like in case of going back from home after signing up
		if 'walletID' not in session:
			raise KeyError

		#Returning the respective home page upon backpage
		conn = mysql.connect()
		cursor = conn.cursor()

#Refreshing Wallet Amount
#%%%  PAXOS HERE  %%%
		tmpData =[]
		dict_data = {'NID':nodeID,'nodekey':NodeKey,'OID':2,"walletID":session['walletID']}

		cursor.execute("SELECT Amount, transactionRank from wallet where walletID = %s;",session['walletID'][7:])
		tmpData = cursor.fetchone()

		update = paxos(2,dict_data)
		if update != 'Fail':
			update = json.loads(update)
		 	if update is not None and (int(update[1]) > int(tmpData[1])):
				tmpData =  update

		update = paxos(3,dict_data)
		if update != 'Fail':
			update = json.loads(update) 
			if update is not None and (int(update[1]) > int(tmpData[1])):
				tmpData =  update

		#update current node database with latest data
		cursor.execute("update wallet set Amount = %s, transactionRank=%s where walletID=%s;",(tmpData[0],tmpData[1],session['walletID'][7:]))
		conn.commit()
#%%%  PAXOS HERE  %%%

		session['amount'] = float(tmpData[0])

		cursor.close()
		conn.close()

		return redirect(url_for('walletHome'))

	except KeyError:

		#In case where walletID doesn't exist in session object, meaning genuine signup GET or POST requests
		if request.method=="POST":
			session['name'] = request.form['name']
			#A random amount is credited to each account upon sign up
			session['amount'] = random.uniform(1.0,100.0)

			conn = mysql.connect()
			cursor = conn.cursor()

#Getting the System Generated WalletID
#%%%  PAXOS HERE  %%%
			dict_data = {'NID':1,'nodekey':NodeKey,'OID':1}

			cursor.execute("SELECT * from wallet order by walletID desc;")
			tmpData = cursor.fetchone()
			if tmpData is None:
				tmpData=0
				flag=0
			else:
				flag = int(tmpData[0])

			cursor.close()
			conn.close()

			conn = mysql.connect()
			cursor = conn.cursor()

			update = paxos(2,dict_data)
			if update != 'Fail':
				update = json.loads(update) 
				if update is not None and int(update[0]) > int(tmpData[0]):
					tmpData =  update

			update = paxos(3,dict_data)
			if update != 'Fail':
				update = json.loads(update) 
				if update is not None and int(update[0]) > int(tmpData[0]):
					tmpData =  update

			#update current node database with latest data if not up-to-date
			if tmpData!=0 and flag < int(tmpData[0]):
				cursor.execute("insert into wallet values (%s,%s,%s,%s,%s,%s);",tmpData)
				conn.commit()
# %%%   PAXOS HERE  %%%


			if tmpData==0:
				session['walletID'] = 'wallet_' + str(1)
			else:
				session['walletID'] = 'wallet_' + str(int(tmpData[0])+1)
				


# %%%   PAXOS HERE  %%%
			#Inserting a new wallet for the customer, seeking consent from other nodes:
			dict_data={'NID':1,'nodekey':NodeKey,'OID':3, 'walletID':session['walletID'],'name':session['name'],
																	'amount':session['amount'],'password':request.form['password']}

			tmpData={}																
			tmpData[2] = paxos(2,dict_data)
			tmpData[3] = paxos(3,dict_data)

			if tmpData[2] == 'OK' or tmpData[3] == 'OK':
				#consensus
				cursor.execute("insert into wallet(walletID,Name,Amount,password) values (%s,%s,%s,%s);",( int(session['walletID'][7:]), 
																			session['name'], float(session['amount']),request.form['password']))
				conn.commit()
			else:
				tmpCommand = "delete from wallet where walletID="+str(session['walletID'][7:])
				dict_data = {'NID':1,'nodekey':NodeKey,'OID':12,'rollback':tmpCommand}
				paxos(2,dict_data)
				paxos(3,dict_data)
				session.clear()
				return render_template('invalid.html')
#%%%  PAXOS HERE  %%%

			cursor.close()
			conn.close()
 
 			return redirect(url_for('walletHome'))

		return render_template('signup.html',form=form)



@app.route('/Login',methods=["GET","POST"])
def login():
	form = LoginForm()

	try:
		# Trying to access walletID field in session object to check if a current session exists, 
		# like in case of going back from home after logging in
		session['walletID']==1

		#Returning the respective home page upon backpage
		return redirect(url_for('walletHome'))

	except KeyError:
		#In case where session object doesn't exist meaning genuine Login GET or POST requests

		if request.method=="POST":

			conn = mysql.connect()
			cursor = conn.cursor()

#%%%  PAXOS HERE  %%%
			cursor.execute("SELECT * from wallet where walletID = %s and password= %s;",(request.form['walletID'][7:],request.form['password']))
			data = cursor.fetchone()

			if data in [None,'Fail']:
				dict_data = {'NID':1, "nodekey":NodeKey, "OID":4,'walletID':request.form['walletID'],'password':request.form['password']}

				data = paxos(2,dict_data)
				if data not in [None,'Fail']:
					data = json.loads(data)
				else:
					data = paxos(3,dict_data)
					if data not in [None,'Fail']:
						data =json.loads(data)
#%%%  PAXOS HERE  %%%


			if data in [None,'Fail']:

				cursor.close()
				conn.close()
				
				return render_template('login.html', form=form, option="WalletID/Password is Wrong. Try Again !!")

			else:
				if data[4]=='yes':
					return render_template('login.html', form=form, option="Already LoggedIn. Single Device Access Permitted")

				session['walletID']=request.form['walletID']

#%%%  PAXOS HERE  %%%
				dict_data = {'NID':1, "nodekey":NodeKey, "OID":5,'walletID':session['walletID']}
				tmpData = {}
				tmpData[2]= paxos(2,dict_data)
				tmpData[3]= paxos(3,dict_data)
				
				if tmpData[2] == 'OK' or tmpData[3]=='OK':
					cursor.execute("update wallet set status='yes' where walletID = %s",(session['walletID'][7:]))
					conn.commit()
				else:
					tmpCommand="update wallet set status='no' where walletID="+str(session['walletID'][7:])
					dict_data = {'NID':1, "nodekey":NodeKey, "OID":12, 'rollback':tmpCommand}
					paxos(2,dict_data)
					paxos(3,dict_data)
					session.clear()
					# return render_template('login.html', form=form, option="Already LoggedIn. Single Device Access Permitted")
#%%%  PAXOS HERE  %%%

				session['name'] = data[1]
				session['amount'] = data[2]

				cursor.close()
				conn.close()

				return redirect(url_for('walletHome'))			

		return render_template('login.html', form=form, option="")



@app.route('/walletHome',methods=["GET","POST"])
def walletHome():

	try:
		session['walletID'] ==1
	except KeyError:
		return redirect(url_for('index'))

	form = WalletForm()
	form2 = LogOutForm()
	form3 = RefreshForm()

	conn = mysql.connect()
	cursor = conn.cursor()

#%%%   PAXOS HERE   %%%
	cursor.execute("Select * from transactions where senderID=%s order by transactionID desc",(session['walletID'][7:]))
	rows = {}
	rows[1] = cursor.fetchall()
	if rows[1] == ():
		lastTransID=0
	else:
		lastTransID=int(rows[1][0][0])

	dict_data = {'NID':1, "nodekey":NodeKey, "OID":6,'walletID':session['walletID'],'lastTransID':lastTransID}
	rows[2] =paxos(2,dict_data)
	
	if rows[2] != 'Fail' and json.loads(rows[2])!=[]:
		rows[1] = rows[1]+tuple(json.loads(rows[2]))
		dict_data['lastTransID'] = int(json.loads(rows[2])[0][0])
		
	rows[3] =paxos(3,dict_data)
	if rows[3] != 'Fail' and json.loads(rows[3])!=[]:
		rows[1] = rows[1] +tuple(json.loads(rows[3]))
#%%%   PAXOS HERE   %%%

	if request.method=="POST":

		if 'logout' in request.form:	

#%%%  PAXOS HERE  %%%

			cursor.execute("update wallet set status='no' where walletID = %s",(session['walletID'][7:]))
			conn.commit()
			dict_data = {'NID':1, "nodekey":NodeKey, "OID":7 ,'walletID':session['walletID']}
			paxos(2,dict_data)
			paxos(3,dict_data)
#%%%  PAXOS HERE  %%%

			cursor.close()
			conn.close()
			session.clear()
			return redirect(url_for('login'))

		elif 'refresh' in request.form:

#%%%  PAXOS HERE  %%%
			tmpData =[]
			dict_data = {'NID':nodeID,'nodekey':NodeKey,'OID':2,"walletID":session['walletID']}

			cursor.execute("SELECT Amount, transactionRank from wallet where walletID = %s;",session['walletID'][7:])
			tmpData = cursor.fetchone()

			update = paxos(2,dict_data)
			if update != 'Fail' and json.loads(update) is not None  :
				update = json.loads(update)
			 	if (int(update[1]) > int(tmpData[1])):
					tmpData =  update

			update = paxos(3,dict_data)
			if update != 'Fail' and json.loads(update) is not None  :
				update = json.loads(update) 
				if (int(update[1]) > int(tmpData[1])):
					tmpData =  update

			#update current node database with latest data
			cursor.execute("update wallet set Amount = %s, transactionRank=%s where walletID=%s;",(float(tmpData[0]),int(tmpData[1]),int(session['walletID'][7:])))
			conn.commit()
#%%%  PAXOS HERE  %%%

			session['amount'] = float(tmpData[0])

#%%%   PAXOS HERE   %%%
			cursor.execute("Select * from transactions where senderID=%s order by transactionID desc",(session['walletID'][7:]))
			rows = {}
			rows[1] = cursor.fetchall()
			if rows[1] == ():
				lastTransID=0
			else:
				lastTransID=int(rows[1][0][0])

			dict_data = {'NID':1, "nodekey":NodeKey, "OID":6,'walletID':session['walletID'],'lastTransID':lastTransID}
			rows[2] =paxos(2,dict_data)
			
			if rows[2] != 'Fail' and json.loads(rows[2])!=[]:
				rows[1] = rows[1]+tuple(json.loads(rows[2]))
				dict_data['lastTransID'] = int(json.loads(rows[2])[0][0])
				
			rows[3] =paxos(3,dict_data)
			if rows[3] != 'Fail' and json.loads(rows[3])!=[]:
				rows[1] = rows[1] +tuple(json.loads(rows[3]))
#%%%   PAXOS HERE   %%%

			cursor.close()
			conn.close()

			return render_template('walletHome.html', message='Status Refreshed !!', session=session, rows =rows[1], form=form, form2=form2, form3=form3)

		else:
			#Making a Transaction

#%%%  PAXOS HERE  %%% 					
			cursor.execute("Select password from wallet where walletID = %s;", (session['walletID'][7:]))
			tmpPass = cursor.fetchone()[0]
#%%%  PAXOS HERE  %%%
			
			if request.form["password"] != tmpPass:
				return render_template('walletHome.html', message = "Your Password is Incorrect. Please Try Again !!", 
															           session=session, rows =rows[1], form = form,form2= form2, form3=form3)

#%%%  PAXOS HERE  %%%
			cursor.execute("Select walletID from wallet where walletID = %s;", (request.form['receiverID'][7:]))
			tmp = cursor.fetchone()
#%%%  PAXOS HERE  %%%

			if tmp is None:
				
				cursor.close()
				conn.close()
				
				return render_template('walletHome.html', message = "Receiver's Wallet ID is not valid", 
															session=session, rows =rows[1], form = form,form2= form2, form3=form3)
			else:

#%%%  PAXOS HERE  %%%
				tmpData =[]
				dict_data = {'NID':nodeID,'nodekey':NodeKey,'OID':2,"walletID":session['walletID']}

				cursor.execute("SELECT Amount, transactionRank from wallet where walletID = %s;",session['walletID'][7:])
				tmpData = cursor.fetchone()

				update = paxos(2,dict_data)
				if update != 'Fail' and json.loads(update) is not None  :
					update = json.loads(update)
				 	if (int(update[1]) > int(tmpData[1])):
						tmpData =  update

				update = paxos(3,dict_data)
				if update != 'Fail' and json.loads(update) is not None  :
					update = json.loads(update) 
					if (int(update[1]) > int(tmpData[1])):
						tmpData =  update

				#update current node database with latest data
				cursor.execute("update wallet set Amount = %s, transactionRank=%s where walletID=%s;",(float(tmpData[0]),int(tmpData[1]),int(session['walletID'][7:])))
				conn.commit()
#%%%  PAXOS HERE  %%%

				if float(request.form['amount'])>float(tmpData[0]):
					
					cursor.close()
					conn.close()

					return render_template('walletHome.html', message="You DO NOT have sufficient funds",
																session=session, rows =rows[1], form = form,form2= form2, form3=form3)
				else:
					#Everything is Fine. Can Proceed with creating a Transaction.

#%%%  PAXOS HERE  %%%
					cursor.execute("Select transactionID from transactions order by transactionID desc;")
					tmpID = cursor.fetchone()
					
					if tmpID is None:
						tmpID = 0
					else:
						tmpID = int(tmpID[0])

					dict_data = {'NID':1,'nodekey':NodeKey,'OID':10}
					update = paxos(2,dict_data)
					if update !='Fail' and json.loads(update) != None:
						if int(json.loads(update)[0])>int(tmpID):
							tmpID = int(json.loads(update)[0])

					update =paxos(3,dict_data)
					if update !='Fail' and json.loads(update) != None:
						if int(json.loads(update)[0])>int(tmpID):
							tmpID = int(json.loads(update)[0])

					cursor.close()
					conn.close()
#%%%  PAXOS HERE  %%%

					tmpID =tmpID+1


#%%%  PAXOS HERE  %%%
					conn = mysql.connect()
					cursor = conn.cursor()

					cursor.execute("Insert into transactions(transactionID, senderID, receiverID, Amount) values (%s,%s,%s,%s);",(tmpID,
										int(session['walletID'][7:]),int(request.form['receiverID'][7:]), float(request.form['amount'])))
					cursor.execute("update wallet set Amount = Amount - %s where walletID = %s;",(
														float(request.form['amount']), int(session['walletID'][7:])))					
					cursor.execute("update wallet set Amount = Amount + %s where walletID = %s;",(
													float(request.form['amount']), int(request.form['receiverID'][7:])))

					dict_data ={'NID':1,'nodekey':NodeKey,'OID':11,'transactionID':tmpID,'walletID':session['walletID'],
																	'receiverID':request.form['receiverID'],'amount':request.form['amount']}

					tmpconsent = [paxos(2,dict_data),paxos(3,dict_data)]												
					if 'OK' in tmpconsent:
							conn.commit()
							tmpconsent = []
					else:
						op1 = "update wallet set Amount = Amount +" + str(request.form['amount']) + "where walletID =" + str(session['walletID']) +";"
						op2 = "update wallet set Amount = Amount -" + str(request.form['amount']) + "where walletID =" + str(request.form['receiverID']) +";"
						op3 = "delete from transaction where transactionID="+str(tmpID)+";"

						dict_data={'NID':1,'nodekey':NodeKey,'OID':12,'op1':op1,'op2':op2,'op3':op3}
						paxos(2,dict_data)
						paxos(3,dict_data)
						print 'Rollback'
						session.clear()
						tmpconsent = []
						return render_template('invalid.html')
#%%%  PAXOS HERE  %%%


#%%%  PAXOS HERE  %%%
					tmpData =[]
					dict_data = {'NID':nodeID,'nodekey':NodeKey,'OID':2,"walletID":session['walletID']}

					cursor.execute("SELECT Amount, transactionRank from wallet where walletID = %s;",session['walletID'][7:])
					tmpData = cursor.fetchone()

					update = paxos(2,dict_data)
					if update != 'Fail' and json.loads(update) is not None  :
						update = json.loads(update)
						
					 	if (int(update[1]) > int(tmpData[1])):
							tmpData =  update

					update = paxos(3,dict_data)
					if update != 'Fail' and json.loads(update) is not None  :
						update = json.loads(update) 
						if (int(update[1]) > int(tmpData[1])):
							tmpData =  update

					#update current node database with latest data
					cursor.execute("update wallet set Amount = %s, transactionRank=%s where walletID=%s;",(float(tmpData[0]),int(tmpData[1]),int(session['walletID'][7:])))
					conn.commit()
#%%%  PAXOS HERE  %%%
					session['amount'] = float(tmpData[0])

#%%%   PAXOS HERE   %%%
					cursor.execute("Select * from transactions where senderID=%s order by transactionID desc",(session['walletID'][7:]))
					rows = {}
					rows[1] = cursor.fetchall()
					if rows[1] == ():
						lastTransID=0
					else:
						lastTransID=int(rows[1][0][0])

					dict_data = {'NID':1, "nodekey":NodeKey, "OID":6,'walletID':session['walletID'],'lastTransID':lastTransID}
					rows[2] =paxos(2,dict_data)
					
					if rows[2] != 'Fail' and json.loads(rows[2])!=[]:
						rows[1] = rows[1]+tuple(json.loads(rows[2]))
						dict_data['lastTransID'] = int(json.loads(rows[2])[0][0])
						
					rows[3] =paxos(3,dict_data)
					if rows[3] != 'Fail' and json.loads(rows[3])!=[]:
						rows[1] = rows[1] +tuple(json.loads(rows[3]))
#%%%   PAXOS HERE   %%%

					cursor.close()
					conn.close()

		
					tmpMessage = "Sent "+str(request.form['amount'])+" Bitcoins to "+ str(request.form['receiverID'])+". Transaction Completed."
					return render_template('walletHome.html', message=tmpMessage, session=session, rows =rows[1], form=form, form2=form2, form3=form3)

	return render_template('walletHome.html', message = "", session=session, rows=rows[1], form = form,form2= form2, form3=form3)


@app.route('/Access', methods=['GET'])
def access():
	conn = mysql.connect()
	cursor = conn.cursor()

#%%%   PAXOS HERE   %%%
	cursor.execute("Select * from transactions order by transactionID desc")
	rows = {}
	rows[1] = cursor.fetchall()

	if rows[1] == () :
		lastTransID=0
	else:
		lastTransID=int(rows[1][0][0])

	dict_data = {'NID':1, "nodekey":NodeKey, "OID":9,'lastTransID':lastTransID}
	rows[2] =paxos(2,dict_data)
	
	if rows[2] !='Fail' and json.loads(rows[2])!=[]:
		rows[1] = rows[1]+tuple(json.loads(rows[2]))
		dict_data['lastTransID'] = int(json.loads(rows[2])[0][0])
		rows[3] =paxos(3,dict_data)

	if rows[2] !='Fail' and json.loads(rows[2])!=[]:
		rows[1] = rows[1] +tuple(json.loads(rows[3]))
#%%%   PAXOS HERE   %%%

	cursor.close()
	conn.close()

	return render_template('access.html', rows = rows[1])



if __name__ =='__main__':
	app.run(host='0.0.0.0',debug=True)

