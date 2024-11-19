from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/eid_data', methods=['POST'])
def receive_eid_data():
    data = request.get_json()
    # Traitement des données
    # Vous pouvez enregistrer les données dans une base de données ou les passer au front-end
    print(data)
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
