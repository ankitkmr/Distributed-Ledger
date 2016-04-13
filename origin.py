# Origin Server or Name Server for Blockchain to route requests 
# from clients to geographically nearest Blockchain Storage Node 

# All clients connect to Origin Server first at PORT 5000

# Origin Server hosts PORT 5000 for routing and 5001 for serving requests
# The rest of the Nodes are at different Geographic Locations

from flask import Flask, session, redirect
from flaskext.mysql import MySQL
import random

app = Flask(__name__)


# Sessions variables are stored client side, on the users browser the content of the variables is encrypted, so users can't
# actually see it. They could edit it, but again, as the content wouldn't be signed with this hash key, it wouldn't be valid
# You need to set a secret key (random text) and keep it secret
app.config['SECRET_KEY']='DBMSProject'

mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'blockchain'
app.config['MYSQL_DATABASE_DB'] = 'BlockChain'
app.config['MYSQL_DATABASE_HOST'] = '127.0.0.1'
app.config['MYSQL_PORT'] = '3306'
mysql.init_app(app)

def distance(lon,lat):
	return ((session['coordinates'][0] - lon)**2 + (session['coordinates'][1]-lat)**2)**0.5

@app.route('/')
def index():
	session['coordinates'] = (random.uniform(-180.0,180.0), random.uniform(-90.0,90.0)) 
	conn = mysql.connect()
	cursor = conn.cursor()

	cursor.execute('Select * from nodes')
	nodes = cursor.fetchall()

	min_dist = -1
	for node in nodes:
		tmp = distance(float(node[1]),float(node[2]))
		if min_dist<0:
			session['node'] = node[3]
			session['nodeID']=node[0]
			min_dist = tmp
		else:
			if min_dist>tmp:
				session['node'] = node[3]
				session['nodeID']=node[0]
				min_dist = tmp

	print "Re-routing to", session['nodeID']
	return redirect(session['node'])

if __name__=='__main__':
	app.run(threaded=True, debug=True)