import numpy as np

def y(x, x_min, x_max, k):
    """
    Calcule y(x) selon la formule donnée.
    
    Parameters:
    -----------
    x : float or array
        Valeur(s) d'entrée
    x_min : float
        Valeur minimale de x
    x_max : float
        Valeur maximale de x
    k : float
        Paramètre de courbure (k > 0)
    
    Returns:
    --------
    float or array
        Résultat de y(x)
    """
    x_array = np.asarray(x, dtype=float)
    if np.isclose(k, 0):
        denom = x_max - x_min
        if denom == 0:
            result = np.zeros_like(x_array)
        else:
            result = (x_array - x_min) / denom
        return result if np.ndim(x_array) else float(result)

    # Calcul du numérateur
    denom = x_max - x_min
    if denom == 0:
        result = np.zeros_like(x_array)
        return result if np.ndim(x_array) else float(result)
    numerateur = np.exp(k * (x_array - x_min) / denom) - 1
    
    # Calcul du dénominateur
    denominateur = np.exp(k) - 1
    
    # Résultat final
    result = numerateur / denominateur
    return result if np.ndim(x_array) else float(result)


# Exemple d'utilisation
if __name__ == "__main__":
    # Paramètres
    x_min = 0
    x_max = 10
    k = 2
    
    # Test avec une seule valeur
    x_test = 5
    resultat = y(x_test, x_min, x_max, k)
    
    # Test avec plusieurs valeurs
    x_array_test = np.linspace(x_min, x_max, 11, 5, 6)
    resultats = y(x_array_test, x_min, x_max, k)
