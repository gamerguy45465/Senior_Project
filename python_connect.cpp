#include <Python.h>
#include <QDebug>

void callPython()
{
    Py_Initialize();

    // Add your script directory to sys.path
    PyRun_SimpleString("import sys; sys.path.append('path/to/py')");

    PyObject *pName = PyUnicode_FromString("myscript");     // myscript.py
    PyObject *pModule = PyImport_Import(pName);
    Py_DECREF(pName);

    if (!pModule) {
        PyErr_Print();
        qDebug() << "Failed to import module";
        Py_Finalize();
        return;
    }

    PyObject *pFunc = PyObject_GetAttrString(pModule, "my_function");
    if (pFunc && PyCallable_Check(pFunc)) {
        PyObject *args = PyTuple_Pack(1, PyLong_FromLong(42));
        PyObject *ret  = PyObject_CallObject(pFunc, args);
        Py_DECREF(args);

        if (!ret) PyErr_Print();
        else {
            long out = PyLong_AsLong(ret);
            Py_DECREF(ret);
            qDebug() << "Python returned" << out;
        }
    } else {
        PyErr_Print();
    }

    Py_XDECREF(pFunc);
    Py_DECREF(pModule);

    Py_Finalize();
}
