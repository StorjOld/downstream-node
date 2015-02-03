from flask import jsonify
import traceback


class NotFoundError(Exception):
    pass


class InvalidParameterError(Exception):
    pass


class HttpHandler(object):

    def __init__(self, logger=None, context=dict()):
        """
        :param logger: the mongolog logger to use
        :param context: a dictionary of extra data to log
            as a context for any exceptions that may occur
        """
        self.response = None
        self.logger = logger
        self.context = context

    def __enter__(self):
        """
        Enters the HttpHandler
        This handler will catch exceptions and jsonify them for
        returning to a client.
        Also supports logging via a mongolog logger
        """
        return self

    def __exit__(self, type, value, tb):
        if (type is not None and self.logger is not None):
            self.logger.log_exception(value, self.context)

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
            traceback.print_exception(type, value, tb)
            self.response.status_code = 500
            return True
        else:
            return
