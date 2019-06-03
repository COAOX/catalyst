import sys
import traceback

from weakref import WeakKeyDictionary

class lazyval(object):
    """Decorator that marks that an attribute of an instance should not be
    computed until needed, and that the value should be memoized.

    Example
    -------

    >>> from catalyst.utils.memoize import lazyval
    >>> class C(object):
    ...     def __init__(self):
    ...         self.count = 0
    ...     @lazyval
    ...     def val(self):
    ...         self.count += 1
    ...         return "val"
    ...
    >>> c = C()
    >>> c.count
    0
    >>> c.val, c.count
    ('val', 1)
    >>> c.val, c.count
    ('val', 1)
    >>> c.val = 'not_val'
    Traceback (most recent call last):
    ...
    AttributeError: Can't set read-only attribute.
    >>> c.val
    'val'
    """
    def __init__(self, get):
        self._get = get
        self._cache = WeakKeyDictionary()

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            return self._cache[instance]
        except KeyError:
            self._cache[instance] = val = self._get(instance)
            return val

    def __set__(self, instance, value):
        raise AttributeError("Can't set read-only attribute.")

    def __delitem__(self, instance):
        del self._cache[instance]



class ZiplineError(Exception):
    msg = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @lazyval
    def message(self):
        return str(self)

    def __str__(self):
        msg = self.msg.format(**self.kwargs)
        return msg

    __unicode__ = __str__
    __repr__ = __str__


def silent_except_hook(exctype, excvalue, exctraceback):
    if exctype in [MarketplacePubAddressEmpty, MarketplaceDatasetNotFound,
                   MarketplaceNoAddressMatch, MarketplaceHTTPRequest,
                   MarketplaceNoCSVFiles, MarketplaceContractDataNoMatch,
                   MarketplaceSubscriptionExpired, MarketplaceJSONError,
                   MarketplaceWalletNotSupported, MarketplaceEmptySignature,
                   MarketplaceRequiresPython3]:
        fn = traceback.extract_tb(exctraceback)[-1][0]
        ln = traceback.extract_tb(exctraceback)[-1][1]
        print("Error traceback: {1} (line {2})\n"
              "{0.__name__}:  {3}".format(exctype, fn, ln, excvalue))
    else:
        sys.__excepthook__(exctype, excvalue, exctraceback)


sys.excepthook = silent_except_hook


class MarketplacePubAddressEmpty(ZiplineError):
    msg = (
        'Please enter your public address to use in the Data Marketplace '
        'in the following file: {filename}'
    ).strip()


class MarketplaceDatasetNotFound(ZiplineError):
    msg = (
        'The dataset "{dataset}" is not registered in the Data Marketplace.'
    ).strip()


class MarketplaceNoAddressMatch(ZiplineError):
    msg = (
        'The address registered with the dataset {dataset}: {address} '
        'does not match any of your addresses.'
    ).strip()


class MarketplaceHTTPRequest(ZiplineError):
    msg = (
        'Request to remote server to {request} failed: {error}'
    ).strip()


class MarketplaceNoCSVFiles(ZiplineError):
    msg = (
        'No CSV files found on {datadir} to upload.'
    )


class MarketplaceContractDataNoMatch(ZiplineError):
    msg = (
        'The information found on the contract does not match the '
        'requested data:\n{params}.'
    )


class MarketplaceSubscriptionExpired(ZiplineError):
    msg = (
        'Your subscription to dataset "{dataset}" expired on {date} '
        'and is no longer active. You have to subscribe again running the '
        'following command:\n'
        'catalyst marketplace subscribe --dataset={dataset}'
    )


class MarketplaceWalletNotSupported(ZiplineError):
    msg = (
        'Wallet {wallet} is not supported.'
    )


class MarketplaceEmptySignature(ZiplineError):
    msg = (
        'Signature cannot be empty.'
    )


class MarketplaceJSONError(ZiplineError):
    msg = (
        'The configuration file {file} is malformed. Please correct '
        'the following error:\n{error}'
    )


class MarketplaceRequiresPython3(ZiplineError):
    msg = (
        '\nCatalyst requires Python3 to access the Enigma Data Marketplace.\n'
        'If you want to use the Data Marketplace, you need to reinstall '
        'Catalyst\nwith Python3. See the documentation website for additional '
        'information.')
