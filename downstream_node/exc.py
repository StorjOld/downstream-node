from flask import jsonify


class NotFoundError(Exception):
    pass


class InvalidParameterError(Exception):
    pass


class HttpHandler(object):
    def __enter__(self):
        self.response = None
        return self

    def __exit__(self, type, value, traceback):
        if (type is NotFoundError):
            self.response = jsonify(status='error',
                                    message=str(value))
            self.response.status_code = 404
            return True
        elif (type is InvalidParameterError):
            self.response = jsonify(status='error',
                                    message=str(value))
            self.response.status_code = 400
            return True
        elif (type is not None):
            self.response = jsonify(status='error',
                                    message='Internal Server Error')
            print('Internal server error: {0}'.format(str(value)))
            self.response.status_code = 500
            return True
        else:
            return
