import React, { Component } from 'react';
import './App.css';
import Table from 'react-bootstrap/Table';
import Modal from "./components/Modal";
import axios from 'axios';

class App extends Component {
    constructor(props) {
        super(props);
        this.state = {
            modal: false,
            viewCompleted: false,
            activeItem: {
                full_names: "",
                practice_number: "",
                notes: ""
            },
            transactionsList: []
        };
    }

    componentDidMount() {
        this.refreshTransactionsList();
    }

    refreshTransactionsList = () => {
        axios
            .get("http://localhost:8888/transactions")
            .then(res => this.setState({ transactionsList: res.data }))
            .catch(err => console.log(err));
    };

    // Toggle the modal
    toggle = () => {
        this.setState({ modal: !this.state.modal });
    }

    // Handle the submission of the form
    handleSubmit = item => {
        this.toggle();
        axios
        .post("http://localhost:8888/transactions", item)
        .then(res => this.refreshTransactionsList());
    }

    createItem = () => {
        const item = { title: "", modal: !this.state.modal };
        this.setState({ activeItem: item, modal: !this.state.modal });
    }

    // Render the list of items
    renderItems = () => {
        const newItems = this.state.transactionsList;
        return (
            <Table striped bordered hover>
                <thead>
                <tr>
                    <th>ID</th>
                    <th>Valid</th>
                    <th>Data</th>
                </tr>
                </thead>
                <tbody>
                    {newItems.map((item, i) => (
                        <tr key={i}>
                            <td>
                                <span className={`todo-title mr-2`} title={item.public_key} key={i}>
                                    {item['id']}
                                </span>
                            </td>
                            <td>
                                <span className={`todo-title mr-2`} title={item.signature} key={i}>
                                    {item['valid'] ? 'True' : 'False'}
                                </span>
                            </td>
                            <td>
                                <span className={`todo-title mr-2`} title={item.transaction_data_string} key={i}>
                                    {item['transaction_data_string']}
                                </span>
                            </td>
                        </tr>
                        ))}
                </tbody>
            </Table>
        );
    };

    render() {
        return (
            <main className="content p-3 mb-2 bg-info">
                <h1 className="text-white text-uppercase text-center my-4">Transactions</h1>
                <div className="row">
                    <div className="col-md-6 col-sm-10 mx-auto p-0">
                        <div className="card p-3">
                            <button onClick={this.createItem} className="btn btn-warning">Add transaction</button>
                        </div>
                        <ul className="list-group list-group-flush">
                            {this.renderItems()}
                        </ul>
                    </div>
                </div>
                <footer className="my-3 mb-2 bg-info text-center text-white">¿ &copy; ?</footer>
                {this.state.modal ? (
                    <Modal activeItem={this.state.activeItem} toggle={this.toggle} onSave={this.handleSubmit} />
                ) : null}
            </main>
         )
    }
}

export default App;
