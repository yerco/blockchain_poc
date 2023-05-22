import React, { Component } from 'react';

import {
    Button,
    Modal,
    ModalHeader,
    ModalBody,
    ModalFooter,
    Form,
    FormGroup,
    Input,
    Label
} from 'reactstrap';

class CustomModal extends Component {
    constructor(props) {
        super(props);
        this.state = {
            activeItem: this.props.activeItem
        }
    }

    // To check if the checkbox is checked or not
    handleChange = e => {
        let { name, value } = e.target;
        const activeItem = { ...this.state.activeItem, [name]: value };
        this.setState({ activeItem });
    }

    render() {
        const { toggle, onSave } = this.props;
        return (
            <Modal isOpen={true} toggle={toggle}>
                <ModalHeader toggle={toggle}>Transaction Data</ModalHeader>
                <ModalBody>
                    <Form>
                        <FormGroup>
                            <Label for="full_names">Full Names</Label>
                            <Input
                                type="text"
                                name="full_names"
                                value={this.state.activeItem.full_names}
                                onChange={this.handleChange}
                                placeholder="Enter Full Names"
                            />
                        </FormGroup>
                        <FormGroup>
                            <Label for="practice_number">Practice Number</Label>
                            <Input
                                type="text"
                                name="practice_number"
                                value={this.state.activeItem.practice_number}
                                onChange={this.handleChange}
                                placeholder="Enter Practice Number"
                            />
                        </FormGroup>
                        <FormGroup>
                            <Label for="notes">Notes</Label>
                            <Input
                                type="text"
                                name="notes"
                                value={this.state.activeItem.notes}
                                onChange={this.handleChange}
                                placeholder="Enter Notes"
                            />
                        </FormGroup>
                    </Form>
                </ModalBody>
                <ModalFooter>
                    <Button color="success" onClick={() => onSave(this.state.activeItem)}>
                        Save
                    </Button>
                </ModalFooter>
            </Modal>
        )
    }
}

export default CustomModal;
