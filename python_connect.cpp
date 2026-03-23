#if __has_include(<Python.h>)
#include <Python.h>
#elif __has_include("C:/Users/Jordan Coleman/AppData/Local/Programs/Python/Python314/include/Python.h")
#include "C:/Users/Jordan Coleman/AppData/Local/Programs/Python/Python314/include/Python.h"
#else
#error "Python.h not found. Expected it in the compiler include path or at C:/Users/Jordan Coleman/AppData/Local/Programs/Python/Python314/include."
#endif

#include <QDir>
#include <QString>

#include "python_connect.h"

#include <mutex>

namespace {

QString takePythonError()
{
    if (!PyErr_Occurred()) {
        return QStringLiteral("Unknown Python error");
    }

    PyObject *type = nullptr;
    PyObject *value = nullptr;
    PyObject *traceback = nullptr;

    PyErr_Fetch(&type, &value, &traceback);
    PyErr_NormalizeException(&type, &value, &traceback);

    QString message = QStringLiteral("Unknown Python error");
    if (value) {
        PyObject *valueText = PyObject_Str(value);
        if (valueText) {
            const char *utf8 = PyUnicode_AsUTF8(valueText);
            if (utf8) {
                message = QString::fromUtf8(utf8);
            }
            Py_DECREF(valueText);
        }
    }

    Py_XDECREF(type);
    Py_XDECREF(value);
    Py_XDECREF(traceback);
    return message;
}

bool ensurePythonInitialized(QString *errorMessage)
{
    static std::mutex initMutex;
    const std::lock_guard<std::mutex> lock(initMutex);

    if (Py_IsInitialized()) {
        return true;
    }

    Py_Initialize();
    if (!Py_IsInitialized()) {
        if (errorMessage) {
            *errorMessage = QStringLiteral("Failed to initialize embedded Python.");
        }
        return false;
    }

    return true;
}

bool appendScriptDirectory(const QString &scriptDirectory, QString *errorMessage)
{
    const QString trimmed = scriptDirectory.trimmed();
    if (trimmed.isEmpty()) {
        return true;
    }

    PyObject *sysPath = PySys_GetObject("path"); // Borrowed reference.
    if (!sysPath || !PyList_Check(sysPath)) {
        if (errorMessage) {
            *errorMessage = QStringLiteral("Unable to access sys.path.");
        }
        return false;
    }

    const QString normalized = QDir::cleanPath(trimmed);
    const QByteArray pathUtf8 = normalized.toUtf8();
    PyObject *pathEntry = PyUnicode_DecodeFSDefault(pathUtf8.constData());
    if (!pathEntry) {
        if (errorMessage) {
            *errorMessage = QStringLiteral("Failed to convert script directory to Python string: %1")
                                .arg(takePythonError());
        }
        return false;
    }

    const int contains = PySequence_Contains(sysPath, pathEntry);
    if (contains == 1) {
        Py_DECREF(pathEntry);
        return true;
    }
    if (contains == -1) {
        if (errorMessage) {
            *errorMessage = QStringLiteral("Failed while checking sys.path: %1")
                                .arg(takePythonError());
        }
        Py_DECREF(pathEntry);
        return false;
    }

    if (PyList_Append(sysPath, pathEntry) != 0) {
        if (errorMessage) {
            *errorMessage = QStringLiteral("Failed to append script directory to sys.path: %1")
                                .arg(takePythonError());
        }
        Py_DECREF(pathEntry);
        return false;
    }

    Py_DECREF(pathEntry);
    return true;
}

} // namespace

bool PythonConnect::callFunctionWithIntArg(const QString &scriptDirectory,
                                           const QString &moduleName,
                                           const QString &functionName,
                                           long inputValue,
                                           long *resultValue,
                                           QString *errorMessage)
{
    if (moduleName.trimmed().isEmpty() || functionName.trimmed().isEmpty()) {
        if (errorMessage) {
            *errorMessage = QStringLiteral("moduleName and functionName must be non-empty.");
        }
        return false;
    }

    if (!ensurePythonInitialized(errorMessage)) {
        return false;
    }

    PyGILState_STATE gil = PyGILState_Ensure();

    bool ok = false;
    PyObject *module = nullptr;
    PyObject *callable = nullptr;
    PyObject *arg = nullptr;
    PyObject *args = nullptr;
    PyObject *result = nullptr;

    do {
        if (!appendScriptDirectory(scriptDirectory, errorMessage)) {
            break;
        }

        const QByteArray moduleUtf8 = moduleName.toUtf8();
        module = PyImport_ImportModule(moduleUtf8.constData());
        if (!module) {
            if (errorMessage) {
                *errorMessage = QStringLiteral("Failed to import module '%1': %2")
                                    .arg(moduleName, takePythonError());
            }
            break;
        }

        const QByteArray functionUtf8 = functionName.toUtf8();
        callable = PyObject_GetAttrString(module, functionUtf8.constData());
        if (!callable || !PyCallable_Check(callable)) {
            if (errorMessage) {
                *errorMessage = QStringLiteral("'%1' is not a callable in module '%2'.")
                                    .arg(functionName, moduleName);
            }
            break;
        }

        arg = PyLong_FromLong(inputValue);
        if (!arg) {
            if (errorMessage) {
                *errorMessage = QStringLiteral("Failed to build Python integer argument: %1")
                                    .arg(takePythonError());
            }
            break;
        }

        args = PyTuple_Pack(1, arg);
        if (!args) {
            if (errorMessage) {
                *errorMessage = QStringLiteral("Failed to build Python argument tuple: %1")
                                    .arg(takePythonError());
            }
            break;
        }

        result = PyObject_CallObject(callable, args);
        if (!result) {
            if (errorMessage) {
                *errorMessage = QStringLiteral("Python call failed for %1.%2(): %3")
                                    .arg(moduleName, functionName, takePythonError());
            }
            break;
        }

        if (resultValue) {
            const long output = PyLong_AsLong(result);
            if (PyErr_Occurred()) {
                if (errorMessage) {
                    *errorMessage = QStringLiteral("Python returned a non-integer result: %1")
                                        .arg(takePythonError());
                }
                break;
            }
            *resultValue = output;
        }

        if (errorMessage) {
            errorMessage->clear();
        }
        ok = true;
    } while (false);

    if (!ok && errorMessage && errorMessage->isEmpty()) {
        *errorMessage = QStringLiteral("Embedded Python call failed.");
    }

    Py_XDECREF(result);
    Py_XDECREF(args);
    Py_XDECREF(arg);
    Py_XDECREF(callable);
    Py_XDECREF(module);

    PyGILState_Release(gil);
    return ok;
}
