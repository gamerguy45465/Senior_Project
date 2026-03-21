#ifndef PYTHON_CONNECT_H
#define PYTHON_CONNECT_H

#include <QString>

namespace PythonConnect {

// Calls module.function(inputValue) from an embedded Python runtime.
// Returns true on success; on failure, returns false and fills errorMessage.
bool callFunctionWithIntArg(const QString &scriptDirectory,
                            const QString &moduleName,
                            const QString &functionName,
                            long inputValue,
                            long *resultValue,
                            QString *errorMessage);

} // namespace PythonConnect

#endif // PYTHON_CONNECT_H
