from exams.views import predictions, results, setup


def exams(request):
    return setup(request)


def results(request):
    from exams.views import results as exam_results

    return exam_results(request)


def predictions(request):
    from exams.views import predictions as exam_predictions

    return exam_predictions(request)

# Create your views here.
